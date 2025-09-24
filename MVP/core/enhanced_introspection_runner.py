"""Enhanced Introspection Runner with integrated continuation detection and experiment management.

This module extends the base introspection runner with:
1. Integration with LLM client improvements (finish_reason detection)
2. Proper continuation logic for truncated responses
3. Enhanced experiment management for the pilot validation
4. Real-time metrics computation and phase detection

Provides a clean interface for the pilot validation experiments while leveraging
all the analytical infrastructure.
"""

import asyncio
import json
import logging
import time
import uuid
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

from backend.core.cognitive_metrics import (
    IntrospectionRecord, RunManifest, new_run_manifest, 
    write_manifest, write_record, SCHEMA_VERSION
)
from backend.core.phase_detection import enrich_records_with_phases
from backend.llm_cognitive_driver import get_llm_cognitive_driver

logger = logging.getLogger(__name__)

class IntrospectionRunner:
    """Enhanced runner with continuation detection and real-time analysis"""
    
    def __init__(self, experiments_dir: Optional[Path] = None):
        if experiments_dir is None:
            experiments_dir = Path("knowledge_storage/experiments")
        self.experiments_dir = experiments_dir
        self.experiments_dir.mkdir(parents=True, exist_ok=True)
    
    async def start_experiment(self, config: Dict[str, Any]) -> str:
        """Start a new introspection experiment with the given configuration"""
        
        # Extract configuration
        condition = config.get("condition", "recursive")
        base_prompt = config.get("base_prompt", "Examine your cognitive processes")
        max_depth = config.get("max_depth", 5)
        temperature = config.get("temperature", 0.7)
        top_p = config.get("top_p", 1.0)
        testing_mode = config.get("testing_mode", False)
        notes = config.get("notes", "")
        
        # Create run manifest
        run_id = str(uuid.uuid4())[:8]
        manifest = new_run_manifest(
            model_id=config.get("model_id", "gpt-4"),
            hyperparameters={"temperature": temperature, "top_p": top_p},
            conditions={"condition": condition},
            notes=notes
        )
        manifest.run_id = run_id  # Override with shorter ID
        
        # Setup directories
        run_dir = self.experiments_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        
        # Save manifest
        manifest_path = run_dir / "manifest.json"
        write_manifest(manifest_path, manifest)
        
        # Initialize records file
        records_path = run_dir / "records.jsonl"
        
        # Get LLM driver
        driver = await get_llm_cognitive_driver(testing_mode=testing_mode)
        
        # Execute introspection experiment
        try:
            await self._execute_introspection_experiment(
                driver=driver,
                run_id=run_id,
                base_prompt=base_prompt,
                max_depth=max_depth,
                temperature=temperature,
                top_p=top_p,
                records_path=records_path,
                condition=condition
            )
            
            # Update manifest with completion
            manifest.end_time = time.time()
            manifest.status = "completed"
            write_manifest(manifest_path, manifest)
            
            # Run phase detection
            await self._enrich_with_phases(records_path, run_dir)
            
            logger.info(f"Experiment {run_id} completed successfully")
            return run_id
            
        except Exception as e:
            # Update manifest with error
            manifest.end_time = time.time()
            manifest.status = "failed"
            manifest.error = str(e)
            write_manifest(manifest_path, manifest)
            
            logger.error(f"Experiment {run_id} failed: {e}")
            raise
    
    async def _execute_introspection_experiment(
        self, 
        driver,
        run_id: str,
        base_prompt: str,
        max_depth: int,
        temperature: float,
        top_p: float,
        records_path: Path,
        condition: str
    ) -> None:
        """Execute the introspection experiment with continuation detection"""
        
        # Context accumulation for recursive conditions
        accumulated_context = base_prompt
        
        for depth in range(1, max_depth + 1):
            logger.info(f"Processing depth {depth}/{max_depth}")
            
            try:
                # Determine context based on condition
                if condition == "single_pass":
                    context = base_prompt
                elif condition in ["shuffled_recursive", "random_order_recursive"]:
                    # For shuffled conditions, add some randomization hint
                    context = f"{accumulated_context}\n\n[Processing depth {depth} in experimental order]"
                else:  # recursive
                    context = accumulated_context
                
                # Generate introspection with continuation detection
                response, metadata = await driver.generate_recursive_introspection(
                    context=context,
                    depth=depth,
                    max_tokens=self._calculate_max_tokens(depth),
                    temperature=temperature,
                    top_p=top_p
                )
                
                # Handle continuation if needed
                if metadata.get("needs_continuation", False):
                    logger.info(f"Response truncated at depth {depth}, implementing continuation")
                    response = await self._handle_continuation(
                        driver=driver,
                        partial_response=response,
                        context=context,
                        depth=depth,
                        temperature=temperature,
                        top_p=top_p,
                        original_metadata=metadata
                    )
                
                # Compute metrics and create record
                record = await self._create_introspection_record(
                    run_id=run_id,
                    depth=depth,
                    content=response,
                    context=context,
                    metadata=metadata,
                    condition=condition
                )
                
                # Write record
                write_record(records_path, record)
                
                # Update accumulated context for next depth (recursive conditions)
                if condition in ["recursive", "shuffled_recursive", "random_order_recursive"]:
                    accumulated_context += f"\n\nDepth {depth} reflection:\n{response}\n"
                
                logger.info(f"Completed depth {depth} - complexity: {record.complexity:.3f}")
                
            except Exception as e:
                logger.error(f"Error at depth {depth}: {e}")
                # Write error record
                error_record = IntrospectionRecord(
                    version=SCHEMA_VERSION,
                    run_id=run_id,
                    depth=depth,
                    timestamp=time.time(),
                    content=f"ERROR: {str(e)}",
                    context_length=len(accumulated_context),
                    complexity=0.0,
                    novelty=0.0,
                    drift=0.0,
                    coherence=0.0,
                    metadata={"error": str(e), "condition": condition}
                )
                write_record(records_path, error_record)
                break
    
    def _calculate_max_tokens(self, depth: int) -> int:
        """Calculate max tokens based on depth"""
        base_tokens = 400
        depth_scaling = 150
        max_cap = 2500
        return min(max_cap, base_tokens + (depth - 1) * depth_scaling)
    
    async def _handle_continuation(
        self,
        driver,
        partial_response: str,
        context: str,
        depth: int,
        temperature: float,
        top_p: float,
        original_metadata: Dict[str, Any]
    ) -> str:
        """Handle continuation for truncated responses"""
        
        # Create continuation prompt
        continuation_prompt = f"""
{context}

Previous partial response (continue from where it was cut off):
{partial_response}

Please continue the introspective analysis from where it left off, maintaining the same depth and quality of reflection.
"""
        
        # Generate continuation
        continuation_response, continuation_metadata = await driver.generate_recursive_introspection(
            context=continuation_prompt,
            depth=depth,
            max_tokens=self._calculate_max_tokens(depth),
            temperature=temperature,
            top_p=top_p
        )
        
        # Combine responses
        full_response = partial_response + " " + continuation_response
        
        logger.info(f"Continuation completed - original: {len(partial_response)}, continuation: {len(continuation_response)}")
        
        return full_response
    
    async def _create_introspection_record(
        self,
        run_id: str,
        depth: int,
        content: str,
        context: str,
        metadata: Dict[str, Any],
        condition: str
    ) -> IntrospectionRecord:
        """Create introspection record with computed metrics"""
        
        # Import metrics computation
        from backend.core.cognitive_metrics import compute_complexity, compute_novelty, compute_drift, compute_coherence
        
        # Compute metrics
        complexity = compute_complexity(content)
        novelty = compute_novelty(content, context)
        drift = compute_drift(content, context) if depth > 1 else 0.0
        coherence = compute_coherence(content)
        
        # Create record
        record = IntrospectionRecord(
            version=SCHEMA_VERSION,
            run_id=run_id,
            depth=depth,
            timestamp=time.time(),
            content=content,
            context_length=len(context),
            complexity=complexity,
            novelty=novelty,
            drift=drift,
            coherence=coherence,
            metadata={
                **metadata,
                "condition": condition,
                "content_length": len(content)
            }
        )
        
        return record
    
    async def _enrich_with_phases(self, records_path: Path, run_dir: Path) -> None:
        """Enrich records with phase detection and save phase analysis"""
        try:
            # Load records
            records = []
            with open(records_path, 'r') as f:
                for line in f:
                    records.append(json.loads(line.strip()))
            
            # Run phase detection
            enriched_records = enrich_records_with_phases(records)
            
            # Rewrite records with phase information
            with open(records_path, 'w') as f:
                for record in enriched_records:
                    f.write(json.dumps(record) + '\n')
            
            # Extract and save phase information
            phases = []
            for record in enriched_records:
                if "phase_info" in record:
                    phases.append({
                        "depth": record["depth"],
                        "phase": record["phase_info"]["phase"],
                        "confidence": record["phase_info"]["confidence"],
                        "transition_point": record["phase_info"].get("transition_point", False)
                    })
            
            phases_path = run_dir / "phases.json"
            with open(phases_path, 'w') as f:
                json.dump(phases, f, indent=2)
            
            logger.info(f"Phase detection completed - {len(phases)} phases identified")
            
        except Exception as e:
            logger.warning(f"Phase detection failed: {e}")