package com.cfd;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.scheduling.annotation.EnableScheduling;

import com.cfd.config.AppProperties;

@SpringBootApplication
@EnableScheduling
@EnableConfigurationProperties(AppProperties.class)
public class CfdApplication {

    public static void main(String[] args) {
        SpringApplication.run(CfdApplication.class, args);
    }
}
