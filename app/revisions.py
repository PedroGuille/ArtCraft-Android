MODES=('reviewed','verified','release','main')
LABELS=('Revisadas · 09/11/2026','Versiones base anteriores','Última versión publicada','Desarrollo · main de GitHub')
def selected_index(settings):
    if 'revision_mode' not in settings:return 0
    value=settings['revision_mode']
    if type(value) is not int:return 0
    schema=settings.get('revision_schema')
    if schema==3:return value if 0<=value<len(MODES) else 0
    if schema==2:return value+1 if 0<=value<3 else 0
    return 3 if value==0 else 1
