import json
import os
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from datetime import datetime
from issues.models import Reporter, Issue, CriticalIssue, LowPriorityIssue

REPORTERS_FILE = 'reporters.json'
ISSUES_FILE = 'issues.json'

def read_json_file(filepath):
    if not os.path.exists(filepath):
        return []
    with open(filepath, 'r') as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []

def write_json_file(filepath, data):
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=4)

@api_view(['GET', 'POST'])
def reporters_view(request):
    reporters = read_json_file(REPORTERS_FILE)
    
    if request.method == 'GET':
        reporter_id = request.query_params.get('id')
        if reporter_id is not None:
            for r in reporters:
                if str(r.get('id')) == str(reporter_id):
                    return Response(r)
            return Response({"error": "Reporter not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(reporters)
        
    elif request.method == 'POST':
        name = request.data.get('name')
        email = request.data.get('email')
        
        reporter = Reporter(name, email)
        try:
            reporter.validate()
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
            
        reporter_dict = reporter.to_dict()
        reporter_dict['id'] = len(reporters) + 1
        
        reporters.append(reporter_dict)
        write_json_file(REPORTERS_FILE, reporters)
        
        return Response(reporter_dict, status=status.HTTP_201_CREATED)

@api_view(['GET', 'POST'])
def issues_view(request):
    issues = read_json_file(ISSUES_FILE)
    
    if request.method == 'GET':
        issue_id = request.query_params.get('id')
        status_param = request.query_params.get('status')
        
        if issue_id is not None:
            for i in issues:
                if str(i.get('id')) == str(issue_id):
                    return Response(i)
            return Response({"error": "Issue not found"}, status=status.HTTP_404_NOT_FOUND)
            
        if status_param is not None:
            filtered_issues = [i for i in issues if i.get('status') == status_param]
            return Response(filtered_issues)
            
        return Response(issues)
        
    elif request.method == 'POST':
        data = request.data
        
        try:
            if data.get('priority') == 'critical':
                issue = CriticalIssue(
                    title=data.get('title'),
                    description=data.get('description'),
                    status=data.get('status'),
                    priority=data.get('priority'),
                    reporter=data.get('reporter')
                )
            elif data.get('priority') == 'low':
                issue = LowPriorityIssue(
                    title=data.get('title'),
                    description=data.get('description'),
                    status=data.get('status'),
                    priority=data.get('priority'),
                    reporter=data.get('reporter')
                )
            else:
                issue = Issue(
                    title=data.get('title'),
                    description=data.get('description'),
                    status=data.get('status'),
                    priority=data.get('priority'),
                    reporter=data.get('reporter')
                )

            issue.validate()
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        response_data = issue.to_dict()
        
        # datetime is not inherently json serializable
        if isinstance(response_data.get('created_at'), datetime):
            response_data['created_at'] = response_data['created_at'].isoformat()
            
        response_data['id'] = len(issues) + 1
        response_data['message'] = issue.describe()
        
        issues.append(response_data)
        write_json_file(ISSUES_FILE, issues)
        
        return Response(response_data, status=status.HTTP_201_CREATED)
