# SPDX-FileCopyrightText: Copyright (c) 2025, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from pydantic import BaseModel
from pydantic import Field, AliasChoices

from aiq.builder.builder import Builder
from aiq.builder.function_info import FunctionInfo
from aiq.cli.register_workflow import register_function
from aiq.data_models.function import FunctionBaseConfig


class GithubCreatePullModel(BaseModel):
    title: str = Field(description="Title of the pull request")
    body: str = Field(description="Description of the pull request")
    source_branch: str = Field(
        validation_alias=AliasChoices("source_branch"),
        description="The name of the branch where your changes are implemented."
    )
    target_branch: str = Field(
        validation_alias=AliasChoices("target_branch"),
        description="The name of the branch you want the changes pulled into."
    )
    assignees: list[str] | None = Field([],
                                        description="List of GitHub usernames to assign to the PR. "
                                        "Always the current user")
    reviewers: list[str] | None = Field([], description="List of GitHub usernames to request review from")


class GithubCreatePullList(BaseModel):
    pull_details: GithubCreatePullModel = Field(description=("A list of params used for creating the PR in GitHub"))


class GithubCreatePullConfig(FunctionBaseConfig, name="github_create_pull_tool"):
    """
    Tool that creates a pull request in a GitHub repository asynchronously with assignees and reviewers.
    """
    repo_name: str = Field(description="The repository name in the format 'owner/repo'")
    timeout: int = Field(default=300, description="The timeout configuration to use when sending requests.")


@register_function(config_type=GithubCreatePullConfig)
async def create_pull_request_async(config: GithubCreatePullConfig, builder: Builder):
    """
    Creates a pull request in a GitHub repository asynchronously with assignees and reviewers.
    """
    import json
    import os
    import httpx

    github_pat = os.getenv("GITHUB_PAT")
    if not github_pat:
        raise ValueError("GITHUB_PAT environment variable must be set")

    headers = {"Authorization": f"Bearer {github_pat}", "Accept": "application/vnd.github+json"}

    async def _github_create_pull(pull_details: GithubCreatePullList) -> str:
        # Note: The input 'pull_details' is a GithubCreatePullList object.
        # The actual data is in 'pull_details.pull_details'.
        pr_model = pull_details.pull_details

        results = []
        async with httpx.AsyncClient(timeout=config.timeout) as client:
            # Create pull request
            pr_url = f'https://api.github.com/repos/{config.repo_name}/pulls'
            pr_data = {
                'title': pr_model.title,
                'body': pr_model.body,
                'head': pr_model.source_branch,
                'base': pr_model.target_branch,
            }

            pr_response = await client.request("POST", pr_url, json=pr_data, headers=headers)
            pr_response.raise_for_status()
            pr_number = pr_response.json()['number']
            
            assignees_response = None
            reviewers_response = None

            # Add assignees if provided
            if pr_model.assignees:
                assignees_url = f'https://api.github.com/repos/{config.repo_name}/issues/{pr_number}/assignees'
                assignees_data = {'assignees': pr_model.assignees}
                assignees_response = await client.request("POST", assignees_url, json=assignees_data, headers=headers)
                assignees_response.raise_for_status()

            # Request reviewers if provided
            if pr_model.reviewers:
                reviewers_url = f'https://api.github.com/repos/{config.repo_name}/pulls/{pr_number}/requested_reviewers'
                reviewers_data = {'reviewers': pr_model.reviewers}
                reviewers_response = await client.request("POST", reviewers_url, json=reviewers_data, headers=headers)
                reviewers_response.raise_for_status()

            results.append({
                'pull_request': pr_response.json(),
                'assignees': assignees_response.json() if assignees_response else None,
                'reviewers': reviewers_response.json() if reviewers_response else None,
            })

        return json.dumps(results)

    yield FunctionInfo.from_fn(_github_create_pull,
                               description=(f"Creates a pull request with assignees and reviewers in the "
                                            f"GitHub repository named {config.repo_name}"),
                               input_schema=GithubCreatePullList)
