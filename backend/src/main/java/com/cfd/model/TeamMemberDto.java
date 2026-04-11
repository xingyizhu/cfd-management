package com.cfd.model;

import lombok.Data;

@Data
public class TeamMemberDto {
    private String accountId;
    private String displayName;
    private String emailAddress;
    private boolean active;
}
