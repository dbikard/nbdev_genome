"""Contains the GenomeBrowser and GenomeStack classes"""

# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/API/00_browser.ipynb.

# %% auto 0
__all__ = ['GenomeBrowser', 'GenomeBrowserModifier', 'HighlightModifier', 'GenomeStack']

# %% ../nbs/API/00_browser.ipynb 4
from fastcore.basics import *

from .track import Track

from genomenotebook.utils import (
    parse_gff,
    parse_fasta,
    parse_genbank,
    add_z_order,
    _save_html,
    _gb_show,
    _save
)

from genomenotebook.plot import (
    GenomePlot,
)

from genomenotebook.glyphs import (
    get_feature_patches, 
    get_default_glyphs,
    _format_attribute
)

from bokeh.models import (
    ColumnDataSource,
    HoverTool, 
    Quad
)

from bokeh.io import output_notebook

output_notebook(hide_banner=True) #|hide_line

import Bio

import numpy as np
import pandas as pd
import warnings
import os
from typing import Union, List, Dict, Optional
from collections.abc import Mapping
from collections import defaultdict

try: #for wsl and/or conda
    import chromedriver_binary
except:
    pass

# %% ../nbs/API/00_browser.ipynb 5
class GenomeBrowser:
    """Initialize a GenomeBrowser object.
    """
    _default_feature_types = ["CDS", "repeat_region", "ncRNA", "rRNA", "tRNA"]
    # _default_attributes = ["gene", "locus_tag", "product"]
    _default_feature_name = "gene"
    def __init__(self,
                 gff_path: str = None, #path to the gff3 file of the annotations (also accepts gzip files)
                 fasta_path: str = None, #path to the fasta file of the genome sequence
                 gb_path: str = None, #path to a genbank file
                 seq_id: str = None, #id of the sequence to load, for genomes with multiple contigs, defaults to the first sequence in the genbank or gff file.
                 init_pos: int = None, #initial position to display
                 init_win: int = 10000, #initial window size (max=20000)
                 bounds: tuple = None, #bounds can be specified. This helps preserve memory by not loading the whole genome if not needed.
                 max_interval: int = 100000, #maximum size of the field of view in bp
                 show_seq: bool = True, #creates a html div that shows the sequence when zooming in
                 search: bool = True, #enables a search bar
                 attributes: Union[list,Dict[str,Optional[list]]] = None , #list of attribute names from the GFF attributes column to be extracted. If dict then keys are feature types and values are lists of attributes. If None, then all attributes will be used.
                 feature_name: Optional[Union[str, Dict[str,str]]] = None, #attribute to be displayed as the feature name. If str then use the same field for every feature type. If dict then keys are feature types and values are feature name attribute.
                 feature_types: list = None, # list of feature types to display
                 glyphs: dict = None, #dictionary defining the type and color of glyphs to display for each feature type
                 height: int = 150, # height of the annotation track
                 width: int = 600, # width of the inner frame of the browser
                 label_angle: int = 45, # angle of the feature names displayed on top of the features
                 label_font_size: str = "10pt", # font size fo the feature names
                 label_justify: str = "center", # center, left
                 label_vertical_offset: float = 0.03, # how far above a feature to draw the label
                 label_horizontal_offset: float = -5, # how far to shift the feature label on the x-axis
                 show_labels: bool = True, # if False, then don't show feature labels
                 feature_height: float = 0.15, #fraction of the annotation track height occupied by the features
                 features:pd.DataFrame = None, # DataFrame with columns: ["seq_id", "source", "type", "start", "end", "score", "strand", "phase", "attributes"], where "attributes" is a dict of attributes.
                 seq:Bio.Seq.Seq = None, # keeps the Biopython sequence object
                 color_attribute: str = None, # feature attribute to be used as patch color
                 z_stack: bool = False, #if true features that overlap will be stacked on top of each other
                 attr_panel: bool = True, #if true creates a panel on the right of the plot to display attributes on click
                 **kwargs, #additional keyword arguments are passed as is to bokeh.plotting.figure
                 ):
        
       
        ### Set attributes based on passed in values ###
        self.gff_path = gff_path
        self.fasta_path = fasta_path
        self.gb_path = gb_path
        self.seq_id = seq_id
        self.init_pos = init_pos
        self.init_win = init_win
        self.bounds = bounds
        self.max_interval = max_interval
        self.show_seq = show_seq
        self.search = search
        self.attributes = attributes
        self.feature_name = feature_name
        if self.feature_name is None:
            self.feature_name = self._default_feature_name
        self.feature_types = feature_types
        self.glyphs = glyphs
        self.height = height
        self.width = width
        self.label_angle = label_angle
        self.label_font_size = label_font_size
        self.label_justify = label_justify
        self.label_vertical_offset = label_vertical_offset
        self.label_horizontal_offset = label_horizontal_offset
        self.show_labels = show_labels
        self.feature_height = feature_height
        self.features = features
        self.seq = seq
        self.color_attribute = color_attribute
        self.z_stack = z_stack
        self.attr_panel = attr_panel
        self.kwargs=kwargs
        
        
        ### assign defaults ###
        if feature_types is None:
            self.feature_types = self._default_feature_types.copy()

        self.attributes = attributes
        # if attributes is None:
        #     self.attributes =  self._default_attributes.copy()
        
        # If attribtues is a list then creates the self.attribtues dictionary with the same attributes list for each feature type
        if isinstance(self.attributes,List):
            self.attributes = {feature_type:self.attributes for feature_type in self.feature_types}

        # Aesthetics
        self.glyphs = get_default_glyphs() if glyphs==None else glyphs
        self.max_glyph_loading_range = 20000
        
        if type(feature_name) is str:
            for feature_type in self.feature_types:
                self.glyphs[feature_type].name_attr = feature_name
        else: # feature_name is None or a dict
            feature_name_dic=defaultdict(lambda: self._default_feature_name)
            if feature_name is not None:
                feature_name_dic.update(feature_name)
            for feature_type in self.feature_types:
                self.glyphs[feature_type].name_attr = feature_name_dic[feature_type]
    

        ### Load sequence and sequence annotations ###

        # TODO: it would be nice to make sequence loading even more lazy, so that bounds and feature selection are not applied until render time,
        # which would allow users to swap out different features and change settings without creating a new GenomeBrowser object.
        # right now it's kind of confusing which properties are mutable and which are not.
        
        if sum(1 for x in [gff_path, gb_path, features] if x is not None) != 1:
            raise ValueError("Exactly one of gff_path, gb_path, or features must be provided")
        elif gff_path:
            self._get_gff_features()
        elif gb_path:
            self._get_genbank_features()
        else: # features supplied as a pandas dataframe
            if not self.seq_id:
                self.seq_id = self.features.loc[0,"seq_id"]
            

        if self.seq is None:
            self.seq_len = self.features.right.max()
        else:
            self.seq_len = len(self.seq)
        
        self.bounds = self.bounds if self.bounds != None else (0, self.seq_len)
        if self.seq is not None:
            self.seq=self.seq[self.bounds[0]:self.bounds[1]]

        if self.init_pos:
            if self.init_pos<self.bounds[0] or self.init_pos>self.bounds[1]:
                warnings.warn("You requested an initial position out of bounds")

        ### initialize visualization ###
        if len(self.features)>0:
            if z_stack:
                add_z_order(self.features)
            self._prepare_data()
        self.tracks = [] # non-gene tracks, such as scatter plots, bar plots, etc.
        self.modifiers = [] # modifiers
    
    def _get_gff_features(self):
        #if seq_id is not provided parse_gff will take the first contig in the file
        self.features = parse_gff(self.gff_path,
                        seq_id=self.seq_id,
                        bounds=self.bounds,
                        feature_types=self.feature_types,
                        attributes=self.attributes
                        )[0]
        self.seq_id = self.seq_id if self.seq_id else self.features.loc[0,"seq_id"]
        self._get_sequence_from_fasta()

    def _get_genbank_features(self):
        self.seq, self.features = parse_genbank(self.gb_path,
                        seq_id=self.seq_id,
                        bounds=self.bounds,
                        feature_types=self.feature_types,
                        attributes=self.attributes
                        )
        self.seq = self.seq[0]
        self.features = self.features[0]
        self.seq_id = self.seq_id if self.seq_id else self.features.loc[0,"seq_id"]
        
        

    def _get_sequence_from_fasta(self):
        """Looks for the sequence matching the seq_id and set bounds.
        """
        #if the sequence is provided then seq_len is the length of the reference sequence before bounds are applied
        #else seq_len is the right of the last feature
        if self.fasta_path != None:
            try:
                self.seq = parse_fasta(self.fasta_path, self.seq_id)
            except:
                warnings.warn(f"genome file {self.fasta_path} cannot be parsed as a fasta file")
                self.show_seq = False #if a sequence is not provided or cannot be parsed then show_seq set to False
        else:
            self.show_seq = False #if a sequence is not provided or cannot be parsed then show_seq set to False


    def _prepare_data(self):
        self.patches = get_feature_patches(self.features, 
                                            self.bounds[0], 
                                            self.bounds[1],
                                            glyphs_dict=self.glyphs,
                                            attributes=self.attributes,
                                            feature_height = self.feature_height,
                                            label_vertical_offset =self.label_vertical_offset,
                                            label_justify=self.label_justify,
                                            color_attribute = self.color_attribute
                                            )

# %% ../nbs/API/00_browser.ipynb 16
@patch
def show(self:GenomeBrowser):
    """
        Shows the plot in an interactive Jupyter notebook
    """
    plot = GenomePlot(self)
    plot._collect_elements()
    _gb_show(plot.elements)

# %% ../nbs/API/00_browser.ipynb 26
@patch
def add_track(self: GenomeBrowser,
             height: int = 200, #size of the track
             tools: str = "xwheel_zoom, ywheel_zoom, pan, box_zoom, save, reset", #comma separated list of Bokeh tools that can be used to navigate the plot
             **kwargs,
             ) -> Track:
    """Adds a track to the GenomeBrowser. Ensures that the x_range are shared and figure widths are identical."""
    t = Track(height=height, 
              tools=tools,
              **kwargs)
    self.tracks.append(t)
    return t
    

# %% ../nbs/API/00_browser.ipynb 29
class GenomeBrowserModifier():
    def __init__(self, gene_track:bool = True, data_tracks:bool = False):
        self.gene_track = gene_track
        self.data_tracks = data_tracks
    
    def apply(self, fig):
      raise NotImplementedError()

# %% ../nbs/API/00_browser.ipynb 30
class HighlightModifier(GenomeBrowserModifier):
    def __init__(self,
        data: pd.DataFrame = None, #pandas DataFrame containing the data
        left_col: str = "left", #name of the column containing the start positions of the regions
        right_col: str = "right", #name of the column containing the end positions of the regions
        color_col: str = "color", #name of the column containing color of the regions
        alpha_col: str = "alpha", #name of the column containing alpha of the regions 
        left = None,
        right = None,
        color = "green",
        alpha: str = 0.2, #transparency
        hover_data: List = None, #list of additional column names to be shown when hovering over the data
        highlight_tracks: bool = False, #whether to highlight just the annotation track or also the other tracks
        **kwargs, #enables to pass keyword arguments used by the Bokeh function
        ):

        self.left_col = left_col
        self.right_col = right_col
        self.color_col = color_col
        self.alpha_col = alpha_col

        if data is None:
            if left is None or right is None or color is None:
                raise ValueError("If `data` is not provided, then left, right, and color must be specified")
            self.data = pd.DataFrame({self.left_col: [left], self.right_col: [right], self.color_col: [color], self.alpha_col: [alpha]})
        else:
            self.data = data.copy() # copy the dataframe because we modify it below, and users might not expect their input to be modified.
        
        if self.color_col not in self.data.columns:
            self.data[self.color_col] = 'green'
        
        if alpha_col not in self.data.columns:
            self.data[self.alpha_col] = alpha

        if left_col not in self.data.columns:
            raise ValueError(f"`left_col` ({self.left_col}) must be in data")
        
        if right_col not in self.data.columns:
            raise ValueError(f"`left_col` ({self.left_col}) must be in data")
        
        if hover_data is None:
            self.hover_data = []
        elif type(hover_data) is str:
            self.hover_data = [hover_data]
        elif type(hover_data) is list:
            self.hover_data = hover_data.copy()
        else:
            raise ValueError("hover_data must be None, str, or List") 

        self.bokeh_args = kwargs
        
        super().__init__(gene_track=True, data_tracks=highlight_tracks)
        
    def render(self, fig, track_mode=False, track_properties=None):
        highlight_source = ColumnDataSource(self.data[[self.left_col,self.right_col,self.color_col,self.alpha_col]+self.hover_data])

        bottom = 0
        top = 1
        if track_mode:
            ylim = track_properties.get("ylim", (0,1))
            if ylim is None:
                ylim = (0,1)
            bottom = ylim[0]
            top = ylim[1]
        
        r = Quad(left=self.left_col, right=self.right_col,
                bottom=bottom,
                top=top,
                fill_color=self.color_col,
                fill_alpha=self.alpha_col,
                line_alpha=0,
                **self.bokeh_args)
        
        renderer = fig.add_glyph(highlight_source, r)
        tooltips=[(f"{self.left_col} - {self.right_col}",f"@{self.left_col} - @{self.right_col}")]+[(f"{attr}",f"@{attr}") for attr in self.hover_data]
        fig.add_tools(HoverTool(renderers=[renderer],
                                        tooltips=tooltips))
    # if highlight_tracks:
    #     for t in self.tracks:
    #         t.highlight(data=data,left=left,right=right,color=color,alpha=alpha,hover_data=hover_data,**kwargs)



# %% ../nbs/API/00_browser.ipynb 31
@patch
def highlight(self:GenomeBrowser,
        data: pd.DataFrame = None, #pandas DataFrame containing the data
        left_col: str = "left", #name of the column containing the start positions of the regions
        right_col: str = "right", #name of the column containing the end positions of the regions
        color_col: str = "color", #name of the column containing color of the regions
        alpha_col: str = "alpha", #name of the column containing alpha (transparency) of the regions 
        left = None,
        right = None,
        color = "green",
        alpha: str = 0.2, #transparency
        hover_data: List = None, #list of additional column names to be shown when hovering over the data
#        highlight_tracks: bool = False, #whether to highlight just the annotation track or also the other tracks
        **kwargs, #enables to pass keyword arguments used by the Bokeh function
        ):
    modifier = HighlightModifier(data, left_col, right_col, color_col, alpha_col, left, right, color, alpha, hover_data, **kwargs)
    self.modifiers.append(modifier)

# %% ../nbs/API/00_browser.ipynb 36
@patch
def add_tooltip_data(self:GenomeBrowser,
                    name: str, #name of the data to be added
                    values: str, #values 
                    feature_type: str = None, #specify the feature type if the data applies only a to specific feature_type  
                    ):

    flt=(self.patches.type == feature_type) | (feature_type is None)
    assert(len(self.patches.loc[flt])==len(values))
    for i,p in self.patches.loc[flt].iterrows():
        self.patches.loc[i,"attributes"] += "<br>"+_format_attribute(name,values[i])


# %% ../nbs/API/00_browser.ipynb 39
@patch
def save_html(self:GenomeBrowser, fname:str, title:str="Genome Plot"):
    plot = GenomePlot(self)
    plot._collect_elements()
    _save_html(plot.elements, fname, title)

# %% ../nbs/API/00_browser.ipynb 40
@patch
def save(self:GenomeBrowser, 
         fname:str, # file name (must end in .svg or . png).\n If using svg, GenomeBrowser needs to be initialized with `output_backend="svg"`
         title:str="Genome Plot" #plot title
        ):
    """Saves the plot in svg or png. This function saves the initial plot that is generated and not the current view of the browser.
    To save in svg format you must initialise your GenomeBrowser using `output_backend="svg"` """

    base_name, ext = os.path.splitext(fname)
    ext = ext.lower()
    if ext not in {".svg", ".png"}:
        raise ValueError(f"filename must end in svg or png, not {ext}")

    output_backend = "webgl"
    if ext == ".svg":
        output_backend = "svg"
    
    plot = GenomePlot(self, output_backend)
    heights = [self.height]
    for track in self.tracks:
        heights.append(track.height)
    
    plot._collect_elements()
    _save(plot.elements, heights, self.width, fname, title)



# %% ../nbs/API/00_browser.ipynb 48
class GenomeStack():
    def __init__(self, browsers = None):
        self.browsers = browsers
        if browsers is None:
            self.browsers = list()


    def get_widest(self):
        """
        returns the index of the widest Browser
        """
        widest = 0
        width = float("-inf")
        for i, browser in enumerate(self.browsers):
            if browser.bounds[1] > width:
                width = browser.bounds[1]
                widest = i
        return widest
    
    def get_elements(self, output_backend:str="webgl"):
        
        plots = [GenomePlot(browser, output_backend=output_backend) for browser in self.browsers]
        widest_i = self.get_widest()
        # print(widest_i)
        # print(self.browsers[widest_i].bounds[1])
        # if len(plots) > 1: # uncomment to hide coordinates on first plot
        #     plots[0].main_fig.xaxis.major_tick_line_color = None
        #     plots[0].main_fig.xaxis.minor_tick_line_color = None
        #     plots[0].main_fig.xaxis.major_label_text_font_size  = '0pt'

        for plot in plots:
            plot.main_fig.x_range = plots[widest_i].main_fig.x_range
            for track_fig in plot.track_figs:
                track_fig.x_range = plots[widest_i].main_fig.x_range
        
        # for i, plot in enumerate(plots[1:]):
        #     i = i+1
            
        #     genome_fig = plot.main_fig
            
        #     if i < len(plots)-1: # uncomment to hide coordinates on all but last plot
        #         genome_fig.xaxis.major_tick_line_color = None
        #         genome_fig.xaxis.minor_tick_line_color = None
        #         genome_fig.xaxis.major_label_text_font_size  = '0pt'

        all_elements = []
        for plot in plots:
            plot._collect_elements()
            all_elements.extend(plot.elements)
        
        return all_elements

    def get_heights(self):
        heights = []
        for browser in self.browsers:
            heights.append(browser.height)
            for track in browser.tracks:
                heights.append(track.height)
        return heights
    
    def show(self):
        elements = self.get_elements()
        _gb_show(elements)
        
    def save_html(self, fname:str, title:str="Genome Plot"):
        elements = self.get_elements()
        save_html(elements, fname, title)
   
    def save(self, 
             fname:str,
             title:str="Genome Plot"
            ):
        """This function saves the initial plot that is generated and not the current view of the browser.
        To save in svg format you must initialise your GenomeBrowser using `output_backend="svg"` """
    
        base_name, ext = os.path.splitext(fname)
        ext = ext.lower()
        if ext not in {".svg", ".png"}:
            raise ValueError(f"filename must end in svg or png, not {ext}")
    
        output_backend = "webgl"
        if ext == ".svg":
            output_backend = "svg"
        
        elements = self.get_elements(output_backend=output_backend)
        heights = self.get_heights()
        save(elements, heights, self.browsers[0].width, fname, title)
        
    @classmethod
    def from_genbank(cls, 
                     genbank_path:str = None, # path to a genbank file
                     **kwargs # arguments to be passed to GenomeBrowser.__init__ for each browser being made
                    ):

        bounds = kwargs.get("bounds", None)        
        feature_types = kwargs.get("feature_types", GenomeBrowser._default_feature_types)
        feature_types = feature_types.copy()
        #attributes = kwargs.get("attributes", GenomeBrowser._default_feature_types)
        attributes = kwargs.get("attributes", None)
        if attributes is not None:
            attibutes = attributes.copy()

        if isinstance(attributes,List):
            attributes = {feature_type:attributes for feature_type in feature_types}
        
        seqs, features = parse_genbank(genbank_path,
                seq_id=None,
                first=False,
                bounds=bounds,
                feature_types=feature_types,
                attributes=attributes
                )
        out = list()
        for seq, feature in zip(seqs, features):
            out.append(GenomeBrowser(features=feature, seq=seq, **kwargs))
            
        
        return cls(out)
            
    
