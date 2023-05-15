# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/API/00_browser.ipynb.

# %% auto 0
__all__ = ['GenomeBrowser']

# %% ../nbs/API/00_browser.ipynb 4
from fastcore.basics import *

from genomenotebook.utils import (
    get_feature_patches, 
    create_genome_browser_plot,
    default_glyphs,
    parse_gff,
)

from genomenotebook.javascript import (
    x_range_change_callback_code, 
    search_callback_code, 
)
from bokeh.models import (
    CustomJS,
    Range1d,
    ColumnDataSource,
    AutocompleteInput,
    Rect,
    Div,
    Styles
)
from bokeh.plotting import show
from bokeh.layouts import column

from Bio import SeqIO

import warnings

# %% ../nbs/API/00_browser.ipynb 5
class GenomeBrowser:
    """Initialize a GenomeBrowser object."""
    def __init__(self,
                 gff_path: str, #path to the gff3 file of the annotations
                 genome_path: str = None, #path to the fasta file of the genome sequence
                 seq_id: str = None, #id of the sequence to show for genomes with multiple contigs
                 init_pos: int = None, #initial position to display
                 init_win: int = 10000, #initial window size (max=20000)
                 bounds: tuple = None, #bounds can be specified. This helps preserve memory by not loading the whole genome if not needed.
                 show_seq: bool = True, #shows the sequence when zooming in
                 search: bool = True, #enables a search bar to lookup a gene name or a DNA sequence
                 attributes: list = ["gene", "locus_tag", "product"], #list of attribute names from the GFF attributes column to be extracted
                 feature_name: str = "gene", #attribute to be displayed as the feature name
                 feature_types: list = ["CDS", "repeat_region", "ncRNA", "rRNA", "tRNA"], # list of feature types to display
                 glyphs: dict = None, #dictionnary defining the type and color of glyphs to display for each feature type
                 **kwargs):
        
        self.gff_path = gff_path
        self.genome_path = genome_path
        self.show_seq = show_seq if genome_path!=None else False
        self.attributes = attributes
        self.feature_types = feature_types
        self.feature_name = feature_name
        self._get_glyphs_dict(glyphs)

        self.features = parse_gff(gff_path,
                                      seq_id=seq_id,
                                      bounds=bounds,
                                      feature_types=feature_types
                                     )
        
        if len(self.features)>0:
            if feature_name not in self.features.columns:
                self.features[feature_name]=""
                
            self.seq_id = self.features.seq_id[0]

            self._get_sequence(bounds)

            if bounds == None: self.bounds=(0,self.seq_len)
            else: self.bounds=bounds

            self._set_init_pos(init_pos)
            self.init_win = min(init_win,self.bounds[1]-self.bounds[0])


            self.max_glyph_loading_range = 20000
            self.frame_width = 600

            self.elements = self._get_browser(**kwargs)
            if search:
                self.elements = [self._get_search_box()]+self.elements

            self.tracks=[] 
        
    def _get_sequence(self, bounds):
        if self.genome_path!=None: 
            rec_found=False
            for rec in SeqIO.parse(self.genome_path, 'fasta'):
                if rec.id==self.seq_id:
                    rec_found=True
                    break

            if not rec_found:
                warnings.warn("seq_id not found in fasta file")
            
            self.rec=rec
            self.seq_len = len(self.rec.seq) #length of the reference sequence before bounds are applied
            if bounds:
                self.rec.seq=self.rec.seq[bounds[0]:bounds[1]]    
        else: 
            self.seq_len = self.features.right.max()
        
        
    def _get_glyphs_dict(self,glyphs):
        if glyphs==None:
            self.glyphs=default_glyphs
        else:
            self.glyphs=glyphs
            
        
    def _set_init_pos(self, init_pos):
        if init_pos == None:
            self.init_pos=sum(self.bounds)//2
        elif init_pos>self.bounds[1] or init_pos<self.bounds[0]:
            warnings.warn("Requested an initial position outside of the browser bounds")
            self.init_pos=sum(self.bounds)//2
        else:
            self.init_pos=init_pos

    def _get_browser(self, **kwargs):

        semi_win = self.init_win / 2
        self.x_range = Range1d(
            max(self.bounds[0],self.init_pos - semi_win), min(self.bounds[1],self.init_pos + semi_win), 
            bounds=self.bounds, 
            max_interval=100000,
            min_interval=40
        )
        
        #Initial glyphs to be plotted by bokeh
        feature_patches = get_feature_patches(self.features, 
                                              self.x_range.start, 
                                              self.x_range.end,
                                              patch_dict=self.glyphs,
                                              attributes=self.attributes,
                                              name = self.feature_name)
        self._glyph_source = ColumnDataSource(feature_patches)
        
        #Glyphs for the whole genome
        self._all_glyphs=get_feature_patches(self.features, 
                                             self.bounds[0], 
                                             self.bounds[1],
                                             patch_dict=self.glyphs,
                                             attributes=self.attributes,
                                             name = self.feature_name)

        #Information about the range currently plotted
        self._loaded_range = ColumnDataSource({"start":[self.x_range.start],
                                                "end":[self.x_range.end], 
                                                "range":[self.max_glyph_loading_range]})

        

        p = create_genome_browser_plot(self._glyph_source, 
                                       self.x_range, 
                                       attributes=self.attributes,
                                       **kwargs)
        p.frame_width=self.frame_width

        sty=Styles(font_size='14px',
                font_family="Courrier",
                color="black",
                display="inline-block",
                background_color = "white",
                margin="0",
                margin_left= "2px",
                )
        
        ## Adding the ability to display the sequence when zooming in
        sequence = {
            'seq': str(self.rec.seq).upper() if self.show_seq else "",
            'bounds':self.bounds
        }

        self._div = Div(height=18, height_policy="fixed", 
                    width=600, width_policy="fixed",
                    styles = sty
                    )
        
        xcb = CustomJS(
            args={
                "x_range": p.x_range,
                "sequence": sequence,
                "all_glyphs":self._all_glyphs,
                "glyph_source": self._glyph_source,
                "div": self._div,
                "loaded_range":self._loaded_range,
            },
            code=x_range_change_callback_code
        )

        p.x_range.js_on_change('start', xcb)
        self.gene_track=p
        self.x_range=p.x_range

        if self.show_seq:
            return [p,self._div]
        else:
            return [p]
        
    def _get_search_box(self):
        ## Create a text input widget for search
        text_input = AutocompleteInput(completions=self._all_glyphs["names"], value="")

        ## Adding BoxAnnotation to highlight search results
        search_span_source = ColumnDataSource({"x":[],"width":[]})#"y":[]
        h=Rect(x='x',y=-2,width='width',height=self.gene_track.height,fill_color='green',fill_alpha=0.2,line_alpha=0)
        self.gene_track.add_glyph(search_span_source, h)

        call_back_search = CustomJS(
            args={
                "x_range": self.x_range,
                "glyph_source": self._glyph_source,
                "bounds": self.bounds,
                "all_glyphs": self._all_glyphs,
                "loaded_range": self._loaded_range,
                "text_input": text_input,
                "search_span_source": search_span_source,
                "div": self._div,
            },
            code=search_callback_code
        )

        text_input.js_on_change('value',call_back_search)#,xcb)

        return text_input
    
    def show(self):
        if hasattr(self,"elements"):
            show(column(self.elements + [t.fig for t in self.tracks]))



# %% ../nbs/API/00_browser.ipynb 25
from .track import Track

# %% ../nbs/API/00_browser.ipynb 26
@patch
def add_track(self:GenomeBrowser,
             height:int = 200, #size of the track
             output_backend="webgl", #can be set to webgl (more efficient) or svg (for figure export)
             ) -> Track:
    """Adds a track to the GenomeBrowser. Ensures that the x_range are shared and figure widths are identical."""
    t = Track(height=height, 
              output_backend=output_backend)
    t.fig.x_range = self.x_range
    t.fig.frame_width = self.frame_width
    t.bounds = self.bounds
    t.loaded_range = ColumnDataSource(self._loaded_range.data)
    t.max_glyph_loading_range = self.max_glyph_loading_range
    self.tracks.append(t)
    return t
    
