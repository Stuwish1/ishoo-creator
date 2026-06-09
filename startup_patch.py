"""
Applicerar syntax-guard patchen på app-modulen.
Anropas vid startup i app.py.
"""


def apply_syntax_guard_patch(app_module):
    """
    Ersätter app_module.apply_and_push med den async-versionen
    som broadcastar syntax_error WS-events.
    """
    from patch_apply_and_push import create_patched_apply_and_push

    patched = create_patched_apply_and_push(
        original_module=app_module,
        manager_ref=app_module.manager,
        load_settings_fn=app_module.load_settings,
        load_pending_fn=app_module.load_pending,
        effective_repo_dir_fn=app_module.effective_repo_dir,
        project_dir_fn=app_module.project_dir,
        git_fn=app_module.git,
    )

    # Ersätt den synkrona apply_and_push med async-versionen
    app_module._apply_and_push_async = patched

    # Uppdatera push_feature endpoint att använda async-versionen
    # Detta görs genom att patcha push_feature-routen
    return patched
