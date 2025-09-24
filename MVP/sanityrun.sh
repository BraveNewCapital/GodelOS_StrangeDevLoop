source mvp_venv/bin/activate
python - <<'PY'
import asyncio
from final_comprehensive_experiment import ComprehensiveExperimentRunner, FINAL_EXPERIMENT_CONFIG
from pathlib import Path
import json

cfg = dict(FINAL_EXPERIMENT_CONFIG)
cfg['base_prompts'] = cfg['base_prompts'][:1]
cfg['conditions'] = ['recursive','single_pass']
cfg['runs_per_condition_per_prompt'] = 1
cfg['max_depth'] = 2
runner = ComprehensiveExperimentRunner(cfg)

async def main():
    await runner.execute_comprehensive_experiments()
    await runner.run_comprehensive_statistical_analysis()
    summary_path = Path('knowledge_storage/experiments/final_comprehensive/comprehensive_statistical_analysis.json')
    print('== Conditions in summary ==')
    print(json.loads(summary_path.read_text())['individual_analyses']['prompt_1']['conditions_analyzed'])
asyncio.run(main())
PY