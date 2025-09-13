# -*- coding: utf-8 -*-
"""
Annotator module for visualizing detected UI elements on screenshots.
"""

import os
import logging
import random
from typing import List
from PIL import Image, ImageDraw, ImageFont
import colorsys

from modules.gemma_client import BoundingBox

logger = logging.getLogger(__name__)

class Annotator:
    """Handles drawing bounding boxes on screenshots."""
    
    def __init__(self, font_path: str = None, font_size: int = 14):
        """
        Initialize the annotator.
        
        Args:
            font_path: Path to a TrueType font file (optional)
            font_size: Font size for labels
        """
        self.font_size = font_size
        self.font = None
        
        # Try to load font if provided
        if font_path and os.path.exists(font_path):
            try:
                self.font = ImageFont.truetype(font_path, font_size)
                logger.info(f"Loaded font from {font_path}")
            except Exception as e:
                logger.warning(f"Failed to load font: {str(e)}. Using default font.")
        
        # Fall back to default font if needed
        if not self.font:
            try:
                # Try to use a default system font
                self.font = ImageFont.load_default()
            except Exception as e:
                logger.warning(f"Failed to load default font: {str(e)}")
        
        logger.info("Annotator initialized")
    
    def _generate_colors(self, n: int):
        """
        Generate visually distinct colors for different UI element types.
        
        Args:
            n: Number of colors to generate
        
        Returns:
            List of RGB color tuples
        """
        colors = []
        for i in range(n):
            # Use HSV color space for better visual distinction
            h = i / n
            s = 0.8
            v = 0.9
            r, g, b = colorsys.hsv_to_rgb(h, s, v)
            colors.append((int(r * 255), int(g * 255), int(b * 255)))
        return colors
    
    def _sanitize_text(self, text: str) -> str:
        """
        Sanitize text to remove characters that might cause rendering issues.
        
        Args:
            text: Original text
            
        Returns:
            Sanitized text safe for rendering
        """
        # Replace problematic Unicode characters with ASCII equivalents
        replacements = {
            '\u2022': '*',  # bullet point
            '\u2018': "'",  # left single quote
            '\u2019': "'",  # right single quote
            '\u201c': '"',  # left double quote
            '\u201d': '"',  # right double quote
            '\u2013': '-',  # en dash
            '\u2014': '--', # em dash
            '\u2026': '...' # ellipsis
        }
        
        for char, replacement in replacements.items():
            text = text.replace(char, replacement)
            
        # As a last resort, remove any remaining non-ASCII characters
        return ''.join(c for c in text if ord(c) < 128)
    
    def draw_bounding_boxes(self, image_path: str, bboxes: List[BoundingBox], output_path: str) -> bool:
        """
        Draw bounding boxes on an image and save the result.
        
        Args:
            image_path: Path to the original screenshot
            bboxes: List of BoundingBox objects to draw
            output_path: Path to save the annotated image
        
        Returns:
            True if successful
        
        Raises:
            IOError: If there's an error processing or saving the image
        """
        try:
            # Ensure output directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Open the image
            image = Image.open(image_path)
            draw = ImageDraw.Draw(image)
            
            # Get unique element types for color assignment
            element_types = list(set(bbox.element_type for bbox in bboxes))
            colors = self._generate_colors(len(element_types))
            color_map = {element_type: colors[i] for i, element_type in enumerate(element_types)}
            
            # Draw each bounding box
            for bbox in bboxes:
                # Get color for this element type
                color = color_map.get(bbox.element_type, (255, 0, 0))  # Red as fallback
                
                # Calculate coordinates for rectangle
                x1, y1 = bbox.x, bbox.y
                x2, y2 = bbox.x + bbox.width, bbox.y + bbox.height
                
                # Draw rectangle with a 3-pixel width
                draw.rectangle([x1, y1, x2, y2], outline=color, width=3)
                
                # Prepare label text
                conf_pct = int(bbox.confidence * 100)
                label = f"{bbox.element_type} {conf_pct}%"
                if bbox.element_text:
                    # Sanitize text to avoid Unicode issues
                    safe_text = self._sanitize_text(bbox.element_text)
                    if len(safe_text) > 20:
                        safe_text = safe_text[:17] + "..."
                    label += f": {safe_text}"
                
                # Sanitize the entire label
                label = self._sanitize_text(label)
                
                try:
                    # Add background for text
                    text_bbox = draw.textbbox((0, 0), label, font=self.font)
                    text_w, text_h = text_bbox[2] - text_bbox[0], text_bbox[3] - text_bbox[1]
                    draw.rectangle([x1, y1 - text_h - 4, x1 + text_w + 4, y1], fill=color)
                    
                    # Draw label text in black
                    draw.text((x1 + 2, y1 - text_h - 2), label, fill=(0, 0, 0), font=self.font)
                except Exception as e:
                    logger.warning(f"Could not render text '{label}': {str(e)}")
                    # Fallback to a very simple label if text rendering fails
                    draw.rectangle([x1, y1 - 15, x1 + 40, y1], fill=color)
            
            # Save the annotated image
            image.save(output_path)
            logger.info(f"Annotated image saved to {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to draw bounding boxes: {str(e)}")
            raise IOError(f"Annotation failed: {str(e)}")