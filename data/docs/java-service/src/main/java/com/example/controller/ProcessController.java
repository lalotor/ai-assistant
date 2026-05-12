package com.example.controller;

import com.example.service.DiffService;
import com.example.model.DiffRequest;
import com.example.model.DiffResponse;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import javax.validation.Valid;
import java.util.HashMap;
import java.util.Map;

/**
 * REST Controller for processing diff computation requests.
 * 
 * Provides endpoints for:
 * - Structural diff computation
 * - Health checks
 * - Service metrics
 * 
 * @author Platform Team
 * @version 2.0.0
 */
@RestController
@RequestMapping("/api")
@CrossOrigin(origins = "*")
public class ProcessController {
    
    private static final Logger logger = LoggerFactory.getLogger(ProcessController.class);
    
    @Autowired
    private DiffService diffService;
    
    /**
     * Process diff computation request.
     * 
     * @param request Diff computation request containing data to compare
     * @return DiffResponse containing computed differences
     */
    @PostMapping("/process")
    public ResponseEntity<DiffResponse> processDiff(@Valid @RequestBody DiffRequest request) {
        logger.info("Received diff computation request: jobId={}", request.getJobId());
        
        try {
            // Validate request
            if (request.getSystemAData() == null || request.getSystemBData() == null) {
                logger.warn("Invalid request: missing data");
                return ResponseEntity.badRequest().build();
            }
            
            // Compute diff
            long startTime = System.currentTimeMillis();
            DiffResponse response = diffService.computeDiff(
                request.getJobId(),
                request.getSystemAData(),
                request.getSystemBData(),
                request.getAlgorithm()
            );
            long duration = System.currentTimeMillis() - startTime;
            
            logger.info("Diff computation completed: jobId={}, duration={}ms, differences={}",
                request.getJobId(), duration, response.getDifferences().size());
            
            return ResponseEntity.ok(response);
            
        } catch (IllegalArgumentException e) {
            logger.error("Invalid request parameters: {}", e.getMessage());
            return ResponseEntity.badRequest().build();
            
        } catch (Exception e) {
            logger.error("Error processing diff computation", e);
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).build();
        }
    }
    
    /**
     * Health check endpoint.
     * 
     * @return Health status and service information
     */
    @GetMapping("/health")
    public ResponseEntity<Map<String, Object>> health() {
        Map<String, Object> health = new HashMap<>();
        health.put("status", "UP");
        health.put("service", "ai-assistant-demo-java");
        health.put("version", "2.0.0");
        health.put("timestamp", System.currentTimeMillis());
        
        return ResponseEntity.ok(health);
    }
    
    /**
     * Service metrics endpoint.
     * 
     * @return Service metrics and statistics
     */
    @GetMapping("/metrics")
    public ResponseEntity<Map<String, Object>> metrics() {
        Map<String, Object> metrics = new HashMap<>();
        
        // Runtime metrics
        Runtime runtime = Runtime.getRuntime();
        Map<String, Object> memory = new HashMap<>();
        memory.put("total", runtime.totalMemory());
        memory.put("free", runtime.freeMemory());
        memory.put("used", runtime.totalMemory() - runtime.freeMemory());
        memory.put("max", runtime.maxMemory());
        
        metrics.put("memory", memory);
        metrics.put("processors", runtime.availableProcessors());
        metrics.put("uptime", System.currentTimeMillis());
        
        return ResponseEntity.ok(metrics);
    }
    
    /**
     * Exception handler for validation errors.
     */
    @ExceptionHandler(IllegalArgumentException.class)
    public ResponseEntity<Map<String, String>> handleValidationException(IllegalArgumentException e) {
        Map<String, String> error = new HashMap<>();
        error.put("error", "validation_error");
        error.put("message", e.getMessage());
        
        return ResponseEntity.badRequest().body(error);
    }
}
