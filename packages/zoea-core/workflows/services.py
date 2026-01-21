import os
from github import Auth, Github


# @citrusgrovetechnology
# ZoeaStudioWorkflow
# Expires on Sat, Dec 20 2025
GH_ACCESS_TOKEN = os.environ.get('ZOEA_STUDIO_GITHUB_API_TOKEN', "gh-access-token")

class PyGithubInterface:

    def __init__(self):
        auth = Auth.Token(GH_ACCESS_TOKEN)
        _gh = Github(auth=auth)
        self.repo = _gh.get_repo("unbracketed/zoea-collab")
    
    def read_issue(self, issue_num: int):
        issue_data = self.repo.get_issue(number=issue_num)
        return issue_data
    
