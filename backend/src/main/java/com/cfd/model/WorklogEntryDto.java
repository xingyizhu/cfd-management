package com.cfd.model;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Data;

@Data
public class WorklogEntryDto {
    @JsonProperty("account_id")
    private String accountId;

    @JsonProperty("display_name")
    private String displayName;

    @JsonProperty("work_date")
    private String workDate;

    @JsonProperty("issue_key")
    private String issueKey;

    @JsonProperty("issue_summary")
    private String issueSummary;

    @JsonProperty("time_sec")
    private long timeSec;

    @JsonProperty("estimated_sec")
    private long estimatedSec;

    @JsonProperty("project_key")
    private String projectKey;

    @JsonProperty("project_name")
    private String projectName;

    @JsonProperty("status_name")
    private String statusName;
}
