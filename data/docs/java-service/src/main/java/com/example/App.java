package com.example;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.Bean;
import org.springframework.web.client.RestTemplate;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * AI Assistant Demo - Java Service
 * Main application entry point for the Spring Boot microservice.
 * 
 * This service provides high-performance diff computation capabilities
 * for the AI Assistant Demo system.
 * 
 * @author Platform Team
 * @version 2.0.0
 * @since 2024-Q4
 */
@SpringBootApplication
public class App {
    
    private static final Logger logger = LoggerFactory.getLogger(App.class);
    
    /**
     * Application entry point.
     * 
     * @param args Command line arguments
     */
    public static void main(String[] args) {
        logger.info("Starting AI Assistant Demo Java Service...");
        logger.info("Version: 2.0.0");
        logger.info("Environment: {}", System.getenv().getOrDefault("ENVIRONMENT", "development"));
        
        try {
            SpringApplication.run(App.class, args);
            logger.info("AI Assistant Demo Java Service started successfully");
        } catch (Exception e) {
            logger.error("Failed to start application", e);
            System.exit(1);
        }
    }
    
    /**
     * Configure RestTemplate bean for HTTP client operations.
     * 
     * @return Configured RestTemplate instance
     */
    @Bean
    public RestTemplate restTemplate() {
        logger.debug("Configuring RestTemplate bean");
        return new RestTemplate();
    }
}
