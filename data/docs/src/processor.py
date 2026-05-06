"""Processor Module - Core job processing and orchestration.

Provides job processing capabilities:
- Async job execution
- Multi-stage processing pipeline
- Error handling and retry logic
- Progress tracking

Author: Platform Team
Version: 2.0.0
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
import json
import time

from comparator import compare
from storage import get_job, update_job_status, store_result
from utils.normalization import normalize_data

# Configure logging
logger = logging.getLogger(__name__)


class ProcessingPipeline:
    """Processing pipeline for job execution."""
    
    def __init__(self, job_id: str):
        """Initialize pipeline.
        
        Args:
            job_id: Job identifier
        """
        self.job_id = job_id
        self.stages = []
    
    def add_stage(self, name: str, handler: callable):
        """Add processing stage.
        
        Args:
            name: Stage name
            handler: Stage handler function
        """
        self.stages.append({'name': name, 'handler': handler})
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute all pipeline stages.
        
        Args:
            context: Processing context
            
        Returns:
            Final processing result
        """
        result = context
        
        for idx, stage in enumerate(self.stages):
            try:
                stage_name = stage['name']
                logger.info(f"Executing stage {idx + 1}/{len(self.stages)}: {stage_name}")
                
                # Update progress
                progress = {
                    'current_stage': stage_name,
                    'stage_number': idx + 1,
                    'total_stages': len(self.stages),
                    'percentage': int((idx / len(self.stages)) * 100)
                }
                
                update_job_status(self.job_id, 'processing', {
                    'progress': progress
                })
                
                # Execute stage
                start_time = time.time()
                result = stage['handler'](result)
                duration = time.time() - start_time
                
                logger.info(f"Stage {stage_name} completed in {duration:.2f}s")
                
            except Exception as e:
                logger.error(f"Stage {stage_name} failed: {str(e)}", exc_info=True)
                raise
        
        return result


def normalize_stage(context: Dict[str, Any]) -> Dict[str, Any]:
    """Normalization stage.
    
    Args:
        context: Processing context
        
    Returns:
        Updated context with normalized data
    """
    try:
        content = context.get('content')
        
        if isinstance(content, str):
            data = json.loads(content)
        else:
            data = content
        
        normalized = normalize_data(data)
        
        context['normalized_data'] = normalized
        context['normalization_applied'] = True
        
        return context
        
    except Exception as e:
        logger.error(f"Normalization failed: {str(e)}", exc_info=True)
        raise


def comparison_stage(context: Dict[str, Any]) -> Dict[str, Any]:
    """Comparison stage.
    
    Args:
        context: Processing context
        
    Returns:
        Updated context with comparison results
    """
    try:
        normalized_data = context.get('normalized_data')
        options = context.get('options', {})
        
        # Get comparison strategy
        strategy = options.get('comparison_algorithm', 'structural')
        
        # For demo, compare against baseline
        baseline = context.get('baseline', normalized_data)
        
        comparison_result = compare(baseline, normalized_data, strategy)
        
        context['comparison_result'] = comparison_result
        
        return context
        
    except Exception as e:
        logger.error(f"Comparison failed: {str(e)}", exc_info=True)
        raise


def finalization_stage(context: Dict[str, Any]) -> Dict[str, Any]:
    """Finalization stage.
    
    Args:
        context: Processing context
        
    Returns:
        Final result
    """
    try:
        comparison_result = context.get('comparison_result', {})
        
        result = {
            'file_id': context.get('file_id'),
            'job_id': context.get('job_id'),
            'match': comparison_result.get('match', False),
            'similarity_score': comparison_result.get('similarity_score', 0.0),
            'differences': comparison_result.get('differences', []),
            'total_changes': comparison_result.get('total_changes', 0),
            'metadata': {
                'normalization_applied': context.get('normalization_applied', False),
                'comparison_strategy': comparison_result.get('comparison_type', 'unknown'),
                'processed_at': datetime.utcnow().isoformat() + 'Z'
            }
        }
        
        return result
        
    except Exception as e:
        logger.error(f"Finalization failed: {str(e)}", exc_info=True)
        raise


def process_job(job_id: str) -> Dict[str, Any]:
    """Process job through complete pipeline.
    
    Args:
        job_id: Job identifier
        
    Returns:
        Processing result
        
    Raises:
        ValueError: If job not found or invalid
    """
    try:
        logger.info(f"Starting processing for job {job_id}")
        
        # Get job details
        job = get_job(job_id)
        
        if not job:
            raise ValueError(f"Job not found: {job_id}")
        
        # Update status to processing
        update_job_status(job_id, 'processing', {
            'started_at': datetime.utcnow().isoformat() + 'Z'
        })
        
        # Build processing context
        context = {
            'job_id': job_id,
            'file_id': job.get('file_id'),
            'content': job.get('content'),
            'options': job.get('options', {}),
            'metadata': job.get('file_metadata', {})
        }
        
        # Create and configure pipeline
        pipeline = ProcessingPipeline(job_id)
        pipeline.add_stage('normalization', normalize_stage)
        pipeline.add_stage('comparison', comparison_stage)
        pipeline.add_stage('finalization', finalization_stage)
        
        # Execute pipeline
        result = pipeline.execute(context)
        
        # Store result
        store_result(job_id, result)
        
        # Update job status to completed
        update_job_status(job_id, 'completed', {
            'completed_at': datetime.utcnow().isoformat() + 'Z',
            'result': result
        })
        
        logger.info(f"Processing completed for job {job_id}")
        
        return result
        
    except Exception as e:
        logger.error(f"Processing failed for job {job_id}: {str(e)}", exc_info=True)
        
        # Update job status to failed
        update_job_status(job_id, 'failed', {
            'failed_at': datetime.utcnow().isoformat() + 'Z',
            'error': {
                'message': str(e),
                'type': type(e).__name__
            }
        })
        
        raise


def process(job: Dict[str, Any]) -> Dict[str, Any]:
    """Simple processing function for backward compatibility.
    
    Args:
        job: Job details or job ID
        
    Returns:
        Processing result
    """
    if isinstance(job, str):
        job_id = job
    else:
        job_id = job.get('job_id')
    
    return process_job(job_id)
