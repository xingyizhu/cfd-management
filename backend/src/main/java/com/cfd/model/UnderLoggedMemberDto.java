package com.cfd.model;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Data;

@Data
public class UnderLoggedMemberDto {

    @JsonProperty("account_id")
    private String accountId;

    private String name;

    @JsonProperty("logged_hours")
    private double loggedHours;

    @JsonProperty("required_hours")
    private double requiredHours;

    @JsonProperty("missing_hours")
    private double missingHours;
}
