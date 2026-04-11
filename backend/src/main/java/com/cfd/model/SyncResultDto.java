package com.cfd.model;

import lombok.Data;

@Data
public class SyncResultDto {
    private int entries;
    private int daily;
    private int weekly;
    private int quarterly;
}
