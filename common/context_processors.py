from common.project_selection import resolve_current_project


def sidebar_projects(request):
    current_project, available_projects = resolve_current_project(request)
    return {
        "current_project": current_project,
        "available_projects": available_projects,
    }
