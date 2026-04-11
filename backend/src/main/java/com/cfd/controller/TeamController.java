package com.cfd.controller;

import com.cfd.client.AtlassianClient;
import com.cfd.model.TeamMemberDto;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api")
@RequiredArgsConstructor
public class TeamController {

    private final AtlassianClient atlassianClient;

    @GetMapping({"/team/members", "/members"})
    public List<TeamMemberDto> getMembers() {
        return atlassianClient.getTeamMembers();
    }
}
