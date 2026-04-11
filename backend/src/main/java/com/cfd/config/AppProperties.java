package com.cfd.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.boot.context.properties.NestedConfigurationProperty;

@Data
@ConfigurationProperties(prefix = "cfd")
public class AppProperties {

    @NestedConfigurationProperty
    private Atlassian atlassian = new Atlassian();

    @NestedConfigurationProperty
    private Supabase supabase = new Supabase();

    @NestedConfigurationProperty
    private Smtp smtp = new Smtp();

    @NestedConfigurationProperty
    private Business business = new Business();

    @NestedConfigurationProperty
    private Scheduler scheduler = new Scheduler();

    @Data
    public static class Atlassian {
        private String userEmail = "";
        private String apiToken = "";
        private String cloudUrl = "https://ddmarketinghub.atlassian.net";
        private String teamId = "";
        private String orgId = "";
    }

    @Data
    public static class Supabase {
        private String url = "";
        private String anonKey = "";
    }

    @Data
    public static class Smtp {
        private String sender = "";
    }

    @Data
    public static class Business {
        private double dailyTargetHours = 7.5;
        private String memberEmailMap = "{}";
        private boolean webuiAutoSyncOnQuery = false;
    }

    @Data
    public static class Scheduler {
        private boolean enabled = false;
        private String syncCron = "0 30 18 * * MON-FRI";
        private String reminderCron = "0 0 19 * * MON-FRI";
        private String zone = "Asia/Shanghai";
    }
}
