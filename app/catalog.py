"""The Craft App Suite source catalog; Android recipes are explicit."""
from dataclasses import dataclass

@dataclass(frozen=True)
class CraftApp:
    id: str
    name: str
    description: str
    extensions: tuple[str, ...]
    recipe: str = 'web'
    owner: str = 'storytold'
    color: str = '#5b75d7'

    @property
    def repository(self): return self.owner+'/'+self.id

OFFICE = ('wordcraft','pdfcraft','gridcraft','deckcraft')
APPS = (
    CraftApp('wordcraft','WordCraft','Documentos de texto',('docx','docm','dotx','doc','odt','rtf','txt','md','html','tex'),'office',color='#4361db'),
    CraftApp('pdfcraft','PDFcraft','Lectura y edición de PDF',('pdf',),'office',color='#dd3657'),
    CraftApp('gridcraft','GridCraft','Hojas de cálculo y datos',('xlsx','xlsm','xls','csv','tsv','ods','xlsb'),'office',color='#238b55'),
    CraftApp('deckcraft','DeckCraft','Presentaciones',('pptx','potx','ppsx','deckcraft'),'office',color='#dd741e'),
    CraftApp('cadcraft','CADCraft','Dibujo técnico y planos',('dwg','dxf','cadcraft'),'native',color='#389ad5'),
    CraftApp('photocraft','PhotoCraft','Imágenes, capas y archivos PSD',('photocraft','psd','ora','png','jpg','jpeg','webp','tif','tiff'),color='#347bec'),
    CraftApp('vectorcraft','VectorCraft','Ilustración vectorial',('vectorcraft','svg','svgz','pdf'),color='#da5944'),
    CraftApp('lightcraft','LightCraft','Fotografía y revelado RAW',('lightcraft','dng','raw','cr2','nef','arw','jpg','jpeg','png'),color='#d49b26'),
    CraftApp('designcraft','DesignCraft','Maquetación y publicaciones',('designcraft','idml','pdf'),color='#769f2a'),
    CraftApp('figcraft','FigCraft','Interfaces y prototipos',('figcraft','fig','svg'),color='#129f7b'),
    CraftApp('soundcraft','SoundCraft','Grabación y edición de audio',('soundcraft','wav','mp3','flac','ogg','aiff','m4a'),color='#2190ae'),
    CraftApp('filmcraft','FilmCraft','Edición de vídeo',('filmcraft','mp4','mov','webm','mkv'),color='#8655d5'),
    CraftApp('effectcraft','EffectCraft','Composición y efectos visuales',('effectcraft','mp4','mov','webm','png','jpg'),color='#ca3b85'),
    CraftApp('craft-anything','Craft Anything','Análisis de software y creación asistida',(),'source',color='#4e7bfb'),
    CraftApp('solidcraft','SolidCraft','CAD paramétrico · Tangency Labs',('slvs','step','stp'),'source','tangency-labs','#459cf0'),
)
BY_ID = {app.id:app for app in APPS}

def selection(mode, ids):
    if mode not in {'lucy','individual'}: raise ValueError('Modo de compilación desconocido.')
    if not isinstance(ids,list) or not ids:
        raise ValueError('Seleccioná al menos una aplicación, sin repetirla.')
    if any(not isinstance(i,str) or i not in BY_ID for i in ids):raise ValueError('Aplicación desconocida.')
    if len(ids)!=len(set(ids)):raise ValueError('No repitas una aplicación.')
    if mode=='lucy' and (len(ids)>4 or any(i not in OFFICE for i in ids)):
        raise ValueError('Lucy admite de uno a cuatro editores: Word, PDF, hojas y presentaciones.')
    return tuple(sorted(ids,key=lambda key:list(BY_ID).index(key)))
