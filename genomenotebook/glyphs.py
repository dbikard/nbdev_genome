"""Contains the Glyph class used to define the different type of glyphs that can be used to represent features, as well the basic plotting functions for GenomeBrowser"""

# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/API/02_glyphs.ipynb.

# %% auto 0
__all__ = ['default_types', 'default_attributes', 'Y_RANGE', 'default_glyphs', 'get_y_range', 'arrow_coordinates',
           'box_coordinates', 'Glyph', 'get_default_glyphs', 'get_patch_coordinates', 'html_wordwrap',
           'get_feature_name', 'get_tooltip', 'get_feature_patches']

# %% ../nbs/API/02_glyphs.ipynb 5
import numpy as np
import pandas as pd

from bokeh.plotting import show as bk_show
from bokeh.layouts import column, row
from bokeh.io import output_notebook, reset_output

from .data import get_example_data_dir
from genomenotebook.utils import (
    parse_gff,
    parse_genbank,
)

import os
from typing import *
import copy
import html
import re

# %% ../nbs/API/02_glyphs.ipynb 6
from collections import defaultdict

# %% ../nbs/API/02_glyphs.ipynb 7
default_types=["CDS", "repeat_region", "ncRNA", "rRNA", "tRNA"]
default_attributes=defaultdict(lambda: ["gene", "locus_tag", "product"])

# %% ../nbs/API/02_glyphs.ipynb 9
Y_RANGE = (0, 1)
def get_y_range() -> tuple:
    """Accessor that returns the Y range for the genome browser plot
    """
    return Y_RANGE

# %% ../nbs/API/02_glyphs.ipynb 10
def arrow_coordinates(feature, 
                      height: float = 1, #relative height of the feature (between 0 and 1)
                      feature_height: float = 0.15, #fraction of the annotation track occupied by the feature glyphs
                      ):
    
    feature_size = feature.right - feature.left
    
    if feature.strand=="+":
        arrow_base = feature.end - np.minimum(feature_size, 100)
        xbox_min = feature.start
    else:
        arrow_base = feature.end + np.minimum(feature_size, 100)
        xbox_min = arrow_base
    
    xs=(feature.start,
        feature.start,
        arrow_base,
        feature.end,
        arrow_base
       )
    
    offset=feature_height*(1-height)/2
    y_min = 0.05+offset
    y_max = 0.05+feature_height-offset
    ys = (y_min, y_max, y_max, (y_max + y_min) / 2, y_min)
    if "z_order" in feature:
        ys = tuple((y+(feature_height*feature["z_order"]) for y in ys))
    return xs, ys, xbox_min


# %% ../nbs/API/02_glyphs.ipynb 11
def box_coordinates(feature, 
                    height: float = 1, #relative height of the feature (between 0 and 1)
                    feature_height: float = 0.15, #fraction of the annotation track occupied by the feature glyphs
                    ):
    xs=(feature.left, feature.left,
        feature.right, feature.right)
    
    offset=feature_height*(1-height)/2
    y_min = 0.05+offset
    y_max = 0.05+feature_height-offset
    ys = (y_min, y_max, y_max, y_min)
    if "z_order" in feature:
        ys = tuple((y+(feature_height*feature["z_order"]) for y in ys))
    return xs, ys, min(xs)

# %% ../nbs/API/02_glyphs.ipynb 12
class Glyph:
    def __init__(self,
                 glyph_type: str ="arrow", # type of the Glyph (arrow or box)
                 colors: tuple = ("purple","orange"), # can be a single color or a tuple of two colors, one for each strand
                 alpha: float = 0.8, #transparency
                 show_name: bool = True, #
                 name_attr: str = default_attributes["CDS"][0], # default attribute to use as the name of the feature to be displayed
                 height: float = 1,  #height of the feature relative to other features (between 0 and 1)
                 ):
        """A class used to define the different types of glyphs shown for different feature types."""
        self.glyph_type=glyph_type
        if type(colors)==str:
            self.colors=(colors,)
        else:
            self.colors=colors

        assert alpha>=0 and alpha <=1
        self.alpha=alpha
        self.show_name=show_name
        self.name_attr=name_attr 
        assert height>0 and height<=1
        self.height=height

        if glyph_type == "box":
            self.coordinates = box_coordinates
        else:
            self.coordinates = arrow_coordinates

    def get_patch(self,
                  feature, # row of a pandas DataFrame extracted from a GFF file
                  feature_height: float = 0.15, #fraction of the annotation track height occupied by the features
                  ):
    
        if len(self.colors)>1:
            color_dic={"+":self.colors[0],
                    "-":self.colors[1]}
        else:
            color_dic=defaultdict(lambda: self.colors[0])

        return self.coordinates(feature, self.height, feature_height), color_dic[feature.strand], self.alpha
    
    def copy(self):
        return copy.deepcopy(self)
    
    def __repr__(self) -> str:
        attributes = ["glyph_type","colors","height","alpha","show_name","name_attr"]
        r=f"Glyph object with attributes:\n"
        for attr in attributes:
            r+=f"\t{attr}: {getattr(self, attr)}\n"
        return r

# %% ../nbs/API/02_glyphs.ipynb 13
def get_default_glyphs(arrow_colors=("purple","orange"), box_colors=("grey",)) -> dict:
    """Returns a dictionnary with:

            * keys: feature types (str)
            * values: a Glyph object
    """
    basic_arrow=Glyph(glyph_type="arrow",colors=arrow_colors,alpha=0.8,show_name=True)
    basic_box=Glyph(glyph_type="box",colors=box_colors,alpha=1,height=0.8,show_name=False)
    
    default_glyphs=defaultdict(lambda: basic_arrow.copy()) #the default glyph will be the same as for CDS etc.
    default_glyphs.update(dict([(f,basic_arrow.copy()) for f in ["CDS", "ncRNA", "rRNA", "tRNA"]]))
    default_glyphs['repeat_region']=basic_box.copy()
    default_glyphs['exon']=basic_box.copy()
    return default_glyphs

default_glyphs=get_default_glyphs()

# %% ../nbs/API/02_glyphs.ipynb 15
def get_patch_coordinates(feature, glyphs_dict, feature_height=0.15, color_attribute=None):
    glyph=glyphs_dict[feature.type]
    coordinate, color, alpha = glyph.get_patch(feature, feature_height=feature_height)
    if color_attribute is not None:
        color = feature.attributes.get(color_attribute, color) # get the color attribute, keep original color if not found.
    return coordinate, color, alpha

# %% ../nbs/API/02_glyphs.ipynb 17
def html_wordwrap(input_string: str, line_len=50, start=0):
    parts = re.split("(\W|,|;|\|)", input_string)
    out = list()
    running_sum = start
    for part in parts:
        if running_sum > line_len:
            out.append("<br>")
            running_sum = 0
        out.append(part)
        running_sum += len(part)

        
    return "".join(out)
    

# %% ../nbs/API/02_glyphs.ipynb 18
def _format_attribute(name, value, color="DodgerBlue", wrap=50):
        return f'<span style="color:{color}">{html.escape(name)}</span><span>: {html_wordwrap(html.escape(str(value)), wrap, len(name)+1)}</span>'


# %% ../nbs/API/02_glyphs.ipynb 20
def get_feature_name(row, glyphs_dict):
    """ For each row of features DataFrame uses the Glyph object provided in the glyphs_dict to know which attribute to use as the name"""
    if glyphs_dict[row.type].show_name:
        if glyphs_dict[row["type"]].name_attr in row.attributes:
            return row.attributes[glyphs_dict[row.type].name_attr]
        elif len(row.attributes) > 0:
                return next(iter(row.attributes.values()))
        
    return ""


# %% ../nbs/API/02_glyphs.ipynb 22
def get_tooltip(feature, attributes, glyph_dict, wrap=50):    
    row_type = feature["type"]
    tooltips = list()
    name = get_feature_name(feature, glyph_dict)
    tooltips.append(f'<span style="color:FireBrick">{name} ({feature["type"]})</span>')

    if attributes is None: # append all
        for attribute in feature["attributes"]:
            tooltips.append(_format_attribute(attribute, feature['attributes'][attribute],wrap=wrap))
    else:
        if row_type in attributes:
            if attributes[row_type] is not None:
                for attribute in attributes[row_type]:
                    if attribute in feature["attributes"]:
                        tooltips.append(_format_attribute(attribute, feature['attributes'][attribute],wrap=wrap))
            else: # append all
                for attribute in feature["attributes"]:
                    tooltips.append(_format_attribute(attribute, feature['attributes'][attribute],wrap=wrap))
    return "<br>".join(tooltips)

# %% ../nbs/API/02_glyphs.ipynb 27
def get_feature_patches(features: pd.DataFrame, #DataFrame of the features 
                        left: int, #left limit
                        right: int, #right limit
                        glyphs_dict: dict, #a dictionary of glyphs to use for each feature type
                        attributes: dict = default_attributes, #dictionary with feature type as keys and a list of attributes to display when hovering as values
                        feature_height: float = 0.15, #fraction of the annotation track height occupied by the features
                        label_vertical_offset: float = 0.05,
                        label_justify: str = "center",
                        color_attribute: str =  None
                       )->pd.DataFrame:
    features=features.loc[(features["right"] > left) & (features["left"] < right)]

    if len(features)>0:
        coordinates, colors, alphas = zip(*features.apply(get_patch_coordinates,
                                                          glyphs_dict=glyphs_dict,
                                                          feature_height=feature_height,
                                                          axis=1, 
                                                          color_attribute=color_attribute))
        xs, ys, xbox_mins = zip(*coordinates)
    else:
        colors = []
        xs, ys = [], []
    
    names=list(features.apply(get_feature_name,glyphs_dict=glyphs_dict, axis=1)
               )
    
    tooltips=list(features.apply(lambda row: get_tooltip(row, attributes, glyphs_dict),
                             axis=1)
                 )

    feature_patches=dict(names=names,
             xs=list(xs),
             ys=list(ys),
             xbox_min=list(xbox_mins),
             color=list(colors),
             alpha=list(alphas),
             pos=list(features.middle.values),
             attributes=tooltips,
             type=features.type
            )
    
    feature_patches=pd.DataFrame(feature_patches)
    
    feature_patches["label_y"] = feature_patches["ys"].map(min) + feature_height + label_vertical_offset
    if label_justify == "center":
        feature_patches["label_x"] = feature_patches.pos
    elif label_justify == "left":
        feature_patches["label_x"] = feature_patches["xbox_min"]
    
    return feature_patches
