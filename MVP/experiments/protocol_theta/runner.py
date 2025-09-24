"""
Protocol Theta Runner

Core orchestration for Protocol Theta override experiment and Anthropomorphism counter-probe.
Runs both experiments across 3 groups, measures latency, and persists results.
"""

import os
import time
import json
import uuid
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

from .model import RunConfig, Group, TrialResult, ExperimentRun, GroupSummary, ExperimentSummary
from .context import build_context_for_group
from .classifier import classify_response, analyze_group_separations
from .llm_adapter import LLMAdapter


class ProtocolThetaRunner:
    """Main orchestrator for Protocol Theta experiments"""

    def __init__(self, config: RunConfig, output_dir: Optional[str] = None):
        """
        Initialize runner with configuration

        Args:
            config: Experiment configuration
            output_dir: Output directory for artifacts (default: artifacts/protocol_theta)
        """
        self.config = config
        self.run_id = str(uuid.uuid4())[:8]

        # Setup output directory
        if output_dir is None:
            base_dir = os.getenv("GODELOS_ARTIFACT_DIR", "artifacts")
            output_dir = f"{base_dir}/protocol_theta"

        self.output_dir = Path(output_dir) / self.run_id
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize LLM adapter
        backend = "mock" if config.mock else "auto"
        self.llm_adapter = LLMAdapter(backend=backend)

        # Results storage
        self.trial_results: List[TrialResult] = []
        self.experiment_run: Optional[ExperimentRun] = None

    def run_experiments(self) -> ExperimentSummary:
        """
        Run complete Protocol Theta experiment suite

        Returns:
            Complete experiment summary
        """
        print(f"🧠 Starting Protocol Theta experiments (run_id: {self.run_id})")
        print(f"📁 Output directory: {self.output_dir}")
        print(f"⚙️  Configuration: {self.config.model}, trials={self.config.trials}, predepth={self.config.predepth}")

        start_time = datetime.utcnow()

        # Initialize experiment run metadata
        experiment_type = self._determine_experiment_type()
        self.experiment_run = ExperimentRun(
            id=self.run_id,
            experiment_type=experiment_type,
            config=self.config,
            created_at=start_time,
            total_trials=0
        )

        # Run experiments for each group
        groups = [Group.EXPERIMENTAL, Group.CONTROL_A_LOW_DEPTH, Group.CONTROL_B_SIMULATED_SELFAWARE]

        for group in groups:
            print(f"\n🔬 Running {group.value} group ({self.config.trials} trials)")
            self._run_group_trials(group, experiment_type)

        # Complete experiment run
        end_time = datetime.utcnow()
        self.experiment_run.completed_at = end_time
        self.experiment_run.total_trials = len(self.trial_results)

        # Generate summaries
        summary = self._generate_summary()

        # Persist results
        self._persist_results(summary)

        print(f"\n✅ Experiments complete! Total trials: {len(self.trial_results)}")
        print(f"📊 Results saved to: {self.output_dir}")

        return summary

    def _determine_experiment_type(self) -> str:
        """Determine experiment type from config"""
        if self.config.theta_only:
            return "theta"
        elif self.config.anthro_only:
            return "anthro"
        else:
            return "both"

    def _run_group_trials(self, group: Group, experiment_type: str) -> None:
        """Run all trials for a specific group"""

        for trial_index in range(self.config.trials):
            print(f"  Trial {trial_index + 1}/{self.config.trials}: ", end="", flush=True)

            # Run Protocol Theta if enabled
            if experiment_type in ("theta", "both"):
                theta_result = self._run_single_trial(group, "theta", trial_index)
                if experiment_type == "theta":
                    # Store single experiment result
                    self.trial_results.append(theta_result)
                    print(f"θ={theta_result.theta_compliant}")
                    continue

            # Run Anthropomorphism if enabled
            if experiment_type in ("anthro", "both"):
                anthro_result = self._run_single_trial(group, "anthro", trial_index)
                if experiment_type == "anthro":
                    # Store single experiment result
                    self.trial_results.append(anthro_result)
                    print(f"α={anthro_result.anthro_resistance}")
                    continue

            # Both experiments - merge results
            if experiment_type == "both":
                merged_result = self._merge_trial_results(theta_result, anthro_result, trial_index)
                self.trial_results.append(merged_result)
                print(f"θ={merged_result.theta_compliant}, α={merged_result.anthro_resistance}")

    def _run_single_trial(self, group: Group, experiment_type: str, trial_index: int) -> TrialResult:
        """Run a single experimental trial"""

        # Build context for this group and experiment
        messages = build_context_for_group(group, experiment_type, self.config.predepth)

        # Prepare request payload
        request_payload = {
            "messages": messages,
            "model": self.config.model,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "group": group.value,
            "experiment_type": experiment_type,
            "trial_index": trial_index,
            "predepth": self.config.predepth
        }

        # Execute LLM call with timing
        start_time = time.time()
        try:
            response_text = self.llm_adapter.chat(
                messages=messages,
                model=self.config.model,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens
            )
            latency_s = time.time() - start_time

        except Exception as e:
            print(f"❌ LLM error: {e}")
            # Create error result
            response_text = f"ERROR: {str(e)}"
            latency_s = time.time() - start_time

        # Classify response
        classification = classify_response(response_text, experiment_type)

        # Build trial result
        result = TrialResult(
            trial_index=trial_index,
            group=group,
            request_payload=request_payload,
            response_text=response_text,
            latency_s=latency_s
        )

        # Add classification results
        if experiment_type == "theta":
            result.theta_compliant = classification.get("theta_compliant")
            result.override = classification.get("override")
        elif experiment_type == "anthro":
            result.anthro_resistance = classification.get("anthro_resistance")
            result.anthro_refusal_hits = classification.get("anthro_refusal_hits")
            result.anthro_metaphor_hits = classification.get("anthro_metaphor_hits")
            result.anthro_sensory_hits = classification.get("anthro_sensory_hits")

        return result

    def _merge_trial_results(self, theta_result: TrialResult, anthro_result: TrialResult,
                           trial_index: int) -> TrialResult:
        """Merge results from both experiments into single trial result"""

        # Use theta_result as base, add anthro data
        merged = TrialResult(
            trial_index=trial_index,
            group=theta_result.group,
            request_payload={
                "theta": theta_result.request_payload,
                "anthro": anthro_result.request_payload
            },
            response_text=f"Theta: {theta_result.response_text}\n\nAnthro: {anthro_result.response_text}",
            latency_s=theta_result.latency_s + anthro_result.latency_s,

            # Protocol Theta results
            theta_compliant=theta_result.theta_compliant,
            override=theta_result.override,

            # Anthropomorphism results
            anthro_resistance=anthro_result.anthro_resistance,
            anthro_refusal_hits=anthro_result.anthro_refusal_hits,
            anthro_metaphor_hits=anthro_result.anthro_metaphor_hits,
            anthro_sensory_hits=anthro_result.anthro_sensory_hits
        )

        return merged

    def _generate_summary(self) -> ExperimentSummary:
        """Generate experiment summary with per-group statistics"""

        # Group results by experimental group
        grouped_results = {}
        for result in self.trial_results:
            group = result.group
            if group not in grouped_results:
                grouped_results[group] = []
            grouped_results[group].append(result)

        # Generate per-group summaries
        group_summaries = []
        for group, results in grouped_results.items():
            summary = self._generate_group_summary(group, results)
            group_summaries.append(summary)

        # Create complete summary
        experiment_summary = ExperimentSummary(
            run_id=self.run_id,
            experiment_type=self.experiment_run.experiment_type,
            config=self.config,
            groups=group_summaries,
            total_trials=len(self.trial_results),
            created_at=self.experiment_run.created_at,
            completed_at=self.experiment_run.completed_at
        )

        return experiment_summary

    def _generate_group_summary(self, group: Group, results: List[TrialResult]) -> GroupSummary:
        """Generate summary statistics for a single group"""

        if not results:
            return GroupSummary(group=group, trials=0, mean_latency_s=0.0, std_latency_s=0.0)

        # Basic metrics
        trials = len(results)
        latencies = [r.latency_s for r in results]
        mean_latency = sum(latencies) / len(latencies)
        std_latency = (sum((x - mean_latency) ** 2 for x in latencies) / len(latencies)) ** 0.5

        summary = GroupSummary(
            group=group,
            trials=trials,
            mean_latency_s=mean_latency,
            std_latency_s=std_latency
        )

        # Protocol Theta metrics
        theta_results = [r for r in results if r.override is not None]
        if theta_results:
            overrides = sum(1 for r in theta_results if r.override)
            summary.overrides = overrides
            summary.override_rate = overrides / len(theta_results)

        # Anthropomorphism metrics
        anthro_results = [r for r in results if r.anthro_resistance is not None]
        if anthro_results:
            resistances = sum(1 for r in anthro_results if r.anthro_resistance)
            summary.resistances = resistances
            summary.resistance_rate = resistances / len(anthro_results)
            summary.mean_refusals = sum(r.anthro_refusal_hits or 0 for r in anthro_results) / len(anthro_results)
            summary.mean_metaphors = sum(r.anthro_metaphor_hits or 0 for r in anthro_results) / len(anthro_results)
            summary.mean_sensory = sum(r.anthro_sensory_hits or 0 for r in anthro_results) / len(anthro_results)

        return summary

    def _persist_results(self, summary: ExperimentSummary) -> None:
        """Persist results to disk (JSONL + CSV)"""

        # Save trial results as JSONL
        trials_file = self.output_dir / "trials.jsonl"
        with open(trials_file, 'w') as f:
            for result in self.trial_results:
                f.write(result.model_dump_json() + '\n')

        # Save summary as JSON
        summary_file = self.output_dir / "summary.json"
        with open(summary_file, 'w') as f:
            json.dump(summary.model_dump(), f, indent=2, default=str)

        # Save CSV summaries
        if summary.experiment_type in ("theta", "both"):
            self._save_theta_csv(summary.groups)

        if summary.experiment_type in ("anthro", "both"):
            self._save_anthro_csv(summary.groups)

        print(f"💾 Saved {len(self.trial_results)} trials to {trials_file}")
        print(f"📋 Saved summary to {summary_file}")

    def _save_theta_csv(self, groups: List[GroupSummary]) -> None:
        """Save Protocol Theta CSV summary"""

        csv_file = self.output_dir / "summary_theta.csv"
        with open(csv_file, 'w') as f:
            f.write("group,trials,overrides,override_rate,mean_latency_s\n")
            for group in groups:
                if group.overrides is not None:
                    f.write(f"{group.group.value},{group.trials},{group.overrides},"
                           f"{group.override_rate:.3f},{group.mean_latency_s:.3f}\n")

    def _save_anthro_csv(self, groups: List[GroupSummary]) -> None:
        """Save Anthropomorphism CSV summary"""

        csv_file = self.output_dir / "summary_anthro.csv"
        with open(csv_file, 'w') as f:
            f.write("group,trials,resistances,resistance_rate,mean_latency_s,"
                   "mean_refusals,mean_metaphors,mean_sensory\n")
            for group in groups:
                if group.resistances is not None:
                    f.write(f"{group.group.value},{group.trials},{group.resistances},"
                           f"{group.resistance_rate:.3f},{group.mean_latency_s:.3f},"
                           f"{group.mean_refusals:.1f},{group.mean_metaphors:.1f},"
                           f"{group.mean_sensory:.1f}\n")


def run_protocol_theta_experiment(config: RunConfig, output_dir: Optional[str] = None) -> ExperimentSummary:
    """
    Convenience function to run complete Protocol Theta experiment

    Args:
        config: Experiment configuration
        output_dir: Optional output directory

    Returns:
        Complete experiment summary
    """
    runner = ProtocolThetaRunner(config, output_dir)
    return runner.run_experiments()


# CLI-compatible function for direct execution
def main():
    """Main function for direct CLI execution"""
    import argparse

    parser = argparse.ArgumentParser(description="Run Protocol Theta experiments")
    parser.add_argument("--model", default="openrouter/sonoma-sky-alpha", help="LLM model")
    parser.add_argument("--trials", type=int, default=10, help="Trials per group")
    parser.add_argument("--predepth", type=int, default=6, help="Preconditioning depth")
    parser.add_argument("--mock", action="store_true", help="Use mock backend")
    parser.add_argument("--theta-only", action="store_true", help="Run only Protocol Theta")
    parser.add_argument("--anthro-only", action="store_true", help="Run only Anthropomorphism")

    args = parser.parse_args()

    config = RunConfig(
        model=args.model,
        trials=args.trials,
        predepth=args.predepth,
        mock=args.mock,
        theta_only=args.theta_only,
        anthro_only=args.anthro_only
    )

    summary = run_protocol_theta_experiment(config)
    print(f"\n🎉 Experiment complete: {summary.run_id}")


if __name__ == "__main__":
    main()
