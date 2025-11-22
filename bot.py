import discord
from discord.ext import commands
import xml.etree.ElementTree as ET
import io
import os
from aiohttp import web
import asyncio
import re

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

async def handle(request):
    return web.Response(text="Bot running!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle)
    app.router.add_get('/health', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get('PORT', 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()


class RBXMLParser:
    """Parses RBXMX XML and extracts properties"""
    
    @staticmethod
    def get_prop(props, name, tag):
        if props is None:
            return None
        for p in props:
            if p.get('name') == name and p.tag == tag:
                return p
        return None
    
    @staticmethod
    def get_string(props, name):
        p = RBXMLParser.get_prop(props, name, 'string')
        return p.text if p is not None and p.text else None
    
    @staticmethod
    def get_bool(props, name):
        p = RBXMLParser.get_prop(props, name, 'bool')
        return p.text == 'true' if p is not None else None
    
    @staticmethod
    def get_float(props, name):
        p = RBXMLParser.get_prop(props, name, 'float')
        if p is not None and p.text:
            return float(p.text)
        p = RBXMLParser.get_prop(props, name, 'double')
        if p is not None and p.text:
            return float(p.text)
        return None
    
    @staticmethod
    def get_int(props, name):
        p = RBXMLParser.get_prop(props, name, 'int')
        if p is not None and p.text:
            return int(p.text)
        return None
    
    @staticmethod
    def get_token(props, name):
        p = RBXMLParser.get_prop(props, name, 'token')
        return int(p.text) if p is not None and p.text else None
    
    @staticmethod
    def get_color3(props, name):
        # Try Color3 format
        p = RBXMLParser.get_prop(props, name, 'Color3')
        if p is not None:
            r = float(p.findtext('R') or 0)
            g = float(p.findtext('G') or 0)
            b = float(p.findtext('B') or 0)
            return (r, g, b)
        # Try Color3uint8 format
        p = RBXMLParser.get_prop(props, name, 'Color3uint8')
        if p is not None and p.text:
            val = int(p.text)
            return ((val >> 16 & 0xFF) / 255, (val >> 8 & 0xFF) / 255, (val & 0xFF) / 255)
        return None
    
    @staticmethod
    def get_udim2(props, name):
        p = RBXMLParser.get_prop(props, name, 'UDim2')
        if p is not None:
            return {
                'xs': float(p.findtext('XS') or 0),
                'xo': float(p.findtext('XO') or 0),
                'ys': float(p.findtext('YS') or 0),
                'yo': float(p.findtext('YO') or 0)
            }
        return None
    
    @staticmethod
    def get_udim(props, name):
        p = RBXMLParser.get_prop(props, name, 'UDim')
        if p is not None:
            return {
                's': float(p.findtext('S') or 0),
                'o': float(p.findtext('O') or 0)
            }
        return None
    
    @staticmethod
    def get_vector2(props, name):
        p = RBXMLParser.get_prop(props, name, 'Vector2')
        if p is not None:
            return (float(p.findtext('X') or 0), float(p.findtext('Y') or 0))
        return None
    
    @staticmethod
    def get_font(props, name):
        p = RBXMLParser.get_prop(props, name, 'Font')
        if p is not None:
            fam = p.find('Family')
            url = 'rbxasset://fonts/families/SourceSansPro.json'
            if fam is not None:
                u = fam.find('url')
                if u is not None and u.text:
                    url = u.text
            weight = p.findtext('Weight') or '400'
            style = p.findtext('Style') or 'Normal'
            return {'url': url, 'weight': weight, 'style': style}
        return None
    
    @staticmethod
    def get_content(props, name):
        p = RBXMLParser.get_prop(props, name, 'Content')
        if p is not None:
            u = p.find('url')
            if u is not None and u.text and u.text not in ['', 'undefined', 'null']:
                return u.text
        return None


class LuaCodeGenerator:
    """Generates clean Lua code in the target style"""
    
    WEIGHT_MAP = {
        '100': 'Thin', '200': 'ExtraLight', '300': 'Light', '400': 'Regular',
        '500': 'Medium', '600': 'SemiBold', '700': 'Bold', '800': 'ExtraBold', '900': 'Heavy'
    }
    
    def __init__(self, scale=1.0):
        self.scale = scale
        self.lines = []
        self.indent = 0
        self.var_counter = 0
        self.used_names = set()
    
    def w(self, line=''):
        self.lines.append('\t' * self.indent + line)
    
    def get_output(self):
        return '\n'.join(self.lines)
    
    def make_var_name(self, name, cls):
        """Create a clean variable name"""
        if name:
            # Clean the name for use as variable
            clean = re.sub(r'[^a-zA-Z0-9]', '', name)
            if clean and not clean[0].isdigit():
                base = clean[0].lower() + clean[1:] if clean else cls.lower()
            else:
                base = cls.lower()
        else:
            base = cls.lower()
        
        # Ensure uniqueness
        var = base
        counter = 1
        while var in self.used_names:
            var = f"{base}{counter}"
            counter += 1
        self.used_names.add(var)
        return var
    
    def scale_int(self, val):
        return int(val * self.scale)
    
    def fmt_color3(self, color):
        return f"Color3.new({round(color[0], 6)}, {round(color[1], 6)}, {round(color[2], 6)})"
    
    def fmt_udim2(self, u, scale_offsets=True):
        xo = self.scale_int(u['xo']) if scale_offsets else int(u['xo'])
        yo = self.scale_int(u['yo']) if scale_offsets else int(u['yo'])
        return f"UDim2.new({u['xs']}, {xo}, {u['ys']}, {yo})"
    
    def fmt_udim(self, u, scale_offset=True):
        o = self.scale_int(u['o']) if scale_offset else int(u['o'])
        return f"UDim.new({u['s']}, {o})"
    
    def escape_string(self, s):
        if not s:
            return ''
        return s.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\r', '')


class UniversalConverter:
    """Main converter class that produces clean Lua output"""
    
    # Token to Enum mappings
    ENUMS = {
        'TextXAlignment': {0: 'Center', 1: 'Left', 2: 'Right'},
        'TextYAlignment': {0: 'Center', 1: 'Top', 2: 'Bottom'},
        'SortOrder': {0: 'Name', 1: 'Custom', 2: 'LayoutOrder'},
        'FillDirection': {0: 'Horizontal', 1: 'Vertical'},
        'HorizontalAlignment': {0: 'Center', 1: 'Left', 2: 'Right'},
        'VerticalAlignment': {0: 'Center', 1: 'Top', 2: 'Bottom'},
        'AutomaticSize': {0: 'None', 1: 'X', 2: 'Y', 3: 'XY'},
        'ScaleType': {0: 'Stretch', 1: 'Slice', 2: 'Tile', 3: 'Fit', 4: 'Crop'},
        'ApplyStrokeMode': {0: 'Contextual', 1: 'Border'},
        'LineJoinMode': {0: 'Round', 1: 'Bevel', 2: 'Miter'},
        'StartCorner': {0: 'TopLeft', 1: 'TopRight', 2: 'BottomLeft', 3: 'BottomRight'},
    }
    
    UI_COMPONENTS = {'UIStroke', 'UICorner', 'UIGradient', 'UIListLayout', 'UIGridLayout', 
                     'UIPadding', 'UIAspectRatioConstraint', 'UISizeConstraint', 'UIScale'}
    
    def __init__(self):
        self.config = {}
        self.parser = RBXMLParser()
        self.gen = None
        self.zindex = 0
    
    def set_config(self, **kwargs):
        self.config = kwargs
    
    def enum_val(self, enum_type, token):
        return self.ENUMS.get(enum_type, {}).get(token, str(token))
    
    def write_frame(self, var, props, parent, is_top_level=False):
        """Write a Frame element"""
        g = self.gen
        p = self.parser
        
        name = p.get_string(props, 'Name')
        if name:
            g.w(f'{var}.Name = "{g.escape_string(name)}"')
        
        size = p.get_udim2(props, 'Size')
        if size:
            g.w(f'{var}.Size = {g.fmt_udim2(size)}')
        
        pos = p.get_udim2(props, 'Position')
        if pos:
            g.w(f'{var}.Position = {g.fmt_udim2(pos)}')
        
        anchor = p.get_vector2(props, 'AnchorPoint')
        if anchor and (anchor[0] != 0 or anchor[1] != 0):
            g.w(f'{var}.AnchorPoint = Vector2.new({anchor[0]}, {anchor[1]})')
        
        bg_color = p.get_color3(props, 'BackgroundColor3')
        if bg_color:
            g.w(f'{var}.BackgroundColor3 = {g.fmt_color3(bg_color)}')
        
        bg_trans = p.get_float(props, 'BackgroundTransparency')
        if bg_trans is not None:
            g.w(f'{var}.BackgroundTransparency = {bg_trans}')
        
        border = p.get_int(props, 'BorderSizePixel')
        if border is not None:
            g.w(f'{var}.BorderSizePixel = {border}')
        
        clip = p.get_bool(props, 'ClipsDescendants')
        if clip:
            g.w(f'{var}.ClipsDescendants = true')
        
        visible = p.get_bool(props, 'Visible')
        if visible is False:
            g.w(f'{var}.Visible = false')
        
        layout_order = p.get_int(props, 'LayoutOrder')
        if layout_order is not None and layout_order != 0:
            g.w(f'{var}.LayoutOrder = {layout_order}')
        
        self.zindex += 1
        g.w(f'{var}.ZIndex = {self.zindex}')
        g.w(f'{var}.Parent = {parent}')
    
    def write_text_element(self, var, props, parent, cls):
        """Write TextLabel, TextButton, or TextBox"""
        g = self.gen
        p = self.parser
        
        name = p.get_string(props, 'Name')
        if name:
            g.w(f'{var}.Name = "{g.escape_string(name)}"')
        
        size = p.get_udim2(props, 'Size')
        if size:
            g.w(f'{var}.Size = {g.fmt_udim2(size)}')
        
        pos = p.get_udim2(props, 'Position')
        if pos:
            g.w(f'{var}.Position = {g.fmt_udim2(pos)}')
        
        anchor = p.get_vector2(props, 'AnchorPoint')
        if anchor and (anchor[0] != 0 or anchor[1] != 0):
            g.w(f'{var}.AnchorPoint = Vector2.new({anchor[0]}, {anchor[1]})')
        
        bg_trans = p.get_float(props, 'BackgroundTransparency')
        if bg_trans is not None:
            g.w(f'{var}.BackgroundTransparency = {bg_trans}')
        
        bg_color = p.get_color3(props, 'BackgroundColor3')
        if bg_color and bg_trans != 1:
            g.w(f'{var}.BackgroundColor3 = {g.fmt_color3(bg_color)}')
        
        border = p.get_int(props, 'BorderSizePixel')
        if border is not None:
            g.w(f'{var}.BorderSizePixel = {border}')
        
        text = p.get_string(props, 'Text')
        if text is not None:
            g.w(f'{var}.Text = "{g.escape_string(text)}"')
        
        text_color = p.get_color3(props, 'TextColor3')
        if text_color:
            g.w(f'{var}.TextColor3 = {g.fmt_color3(text_color)}')
        
        text_size = p.get_int(props, 'TextSize')
        if text_size:
            g.w(f'{var}.TextSize = {g.scale_int(text_size)}')
        
        font = p.get_font(props, 'FontFace')
        if font:
            weight = g.WEIGHT_MAP.get(font['weight'], 'Regular')
            g.w(f'{var}.FontFace = Font.new("{font["url"]}", Enum.FontWeight.{weight}, Enum.FontStyle.{font["style"]})')
        
        text_x = p.get_token(props, 'TextXAlignment')
        if text_x is not None:
            g.w(f'{var}.TextXAlignment = Enum.TextXAlignment.{self.enum_val("TextXAlignment", text_x)}')
        
        text_y = p.get_token(props, 'TextYAlignment')
        if text_y is not None:
            g.w(f'{var}.TextYAlignment = Enum.TextYAlignment.{self.enum_val("TextYAlignment", text_y)}')
        
        text_wrapped = p.get_bool(props, 'TextWrapped')
        if text_wrapped:
            g.w(f'{var}.TextWrapped = true')
        
        text_scaled = p.get_bool(props, 'TextScaled')
        if text_scaled:
            g.w(f'{var}.TextScaled = true')
        
        text_trans = p.get_float(props, 'TextTransparency')
        if text_trans is not None and text_trans != 0:
            g.w(f'{var}.TextTransparency = {text_trans}')
        
        rich = p.get_bool(props, 'RichText')
        if rich:
            g.w(f'{var}.RichText = true')
        
        # TextBox specific
        if cls == 'TextBox':
            placeholder = p.get_string(props, 'PlaceholderText')
            if placeholder:
                g.w(f'{var}.PlaceholderText = "{g.escape_string(placeholder)}"')
            clear = p.get_bool(props, 'ClearTextOnFocus')
            if clear is False:
                g.w(f'{var}.ClearTextOnFocus = false')
        
        # Button specific
        if cls in ['TextButton', 'ImageButton']:
            auto_color = p.get_bool(props, 'AutoButtonColor')
            if auto_color is False:
                g.w(f'{var}.AutoButtonColor = false')
        
        self.zindex += 1
        g.w(f'{var}.ZIndex = {self.zindex}')
        g.w(f'{var}.Parent = {parent}')
    
    def write_image_element(self, var, props, parent, cls):
        """Write ImageLabel or ImageButton"""
        g = self.gen
        p = self.parser
        
        name = p.get_string(props, 'Name')
        if name:
            g.w(f'{var}.Name = "{g.escape_string(name)}"')
        
        size = p.get_udim2(props, 'Size')
        if size:
            g.w(f'{var}.Size = {g.fmt_udim2(size)}')
        
        pos = p.get_udim2(props, 'Position')
        if pos:
            g.w(f'{var}.Position = {g.fmt_udim2(pos)}')
        
        anchor = p.get_vector2(props, 'AnchorPoint')
        if anchor and (anchor[0] != 0 or anchor[1] != 0):
            g.w(f'{var}.AnchorPoint = Vector2.new({anchor[0]}, {anchor[1]})')
        
        bg_color = p.get_color3(props, 'BackgroundColor3')
        if bg_color:
            g.w(f'{var}.BackgroundColor3 = {g.fmt_color3(bg_color)}')
        
        bg_trans = p.get_float(props, 'BackgroundTransparency')
        if bg_trans is not None:
            g.w(f'{var}.BackgroundTransparency = {bg_trans}')
        
        border = p.get_int(props, 'BorderSizePixel')
        if border is not None:
            g.w(f'{var}.BorderSizePixel = {border}')
        
        image = p.get_content(props, 'Image')
        if image:
            g.w(f'{var}.Image = "{image}"')
        
        image_color = p.get_color3(props, 'ImageColor3')
        if image_color:
            g.w(f'{var}.ImageColor3 = {g.fmt_color3(image_color)}')
        
        image_trans = p.get_float(props, 'ImageTransparency')
        if image_trans is not None and image_trans != 0:
            g.w(f'{var}.ImageTransparency = {image_trans}')
        
        scale_type = p.get_token(props, 'ScaleType')
        if scale_type is not None and scale_type != 0:
            g.w(f'{var}.ScaleType = Enum.ScaleType.{self.enum_val("ScaleType", scale_type)}')
        
        if cls == 'ImageButton':
            auto_color = p.get_bool(props, 'AutoButtonColor')
            if auto_color is False:
                g.w(f'{var}.AutoButtonColor = false')
        
        self.zindex += 1
        g.w(f'{var}.ZIndex = {self.zindex}')
        g.w(f'{var}.Parent = {parent}')
    
    def write_scrolling_frame(self, var, props, parent):
        """Write ScrollingFrame"""
        g = self.gen
        p = self.parser
        
        name = p.get_string(props, 'Name')
        if name:
            g.w(f'{var}.Name = "{g.escape_string(name)}"')
        
        size = p.get_udim2(props, 'Size')
        if size:
            g.w(f'{var}.Size = {g.fmt_udim2(size)}')
        
        pos = p.get_udim2(props, 'Position')
        if pos:
            g.w(f'{var}.Position = {g.fmt_udim2(pos)}')
        
        bg_trans = p.get_float(props, 'BackgroundTransparency')
        if bg_trans is not None:
            g.w(f'{var}.BackgroundTransparency = {bg_trans}')
        
        border = p.get_int(props, 'BorderSizePixel')
        if border is not None:
            g.w(f'{var}.BorderSizePixel = {border}')
        
        canvas = p.get_udim2(props, 'CanvasSize')
        if canvas:
            g.w(f'{var}.CanvasSize = {g.fmt_udim2(canvas)}')
        
        scroll_thick = p.get_int(props, 'ScrollBarThickness')
        if scroll_thick is not None:
            g.w(f'{var}.ScrollBarThickness = {g.scale_int(scroll_thick)}')
        
        self.zindex += 1
        g.w(f'{var}.ZIndex = {self.zindex}')
        g.w(f'{var}.Parent = {parent}')
    
    def write_ui_stroke(self, var, props, parent):
        """Write UIStroke component"""
        g = self.gen
        p = self.parser
        
        color = p.get_color3(props, 'Color')
        if color:
            g.w(f'{var}.Color = {g.fmt_color3(color)}')
        
        thickness = p.get_float(props, 'Thickness')
        if thickness is not None:
            g.w(f'{var}.Thickness = {thickness * self.gen.scale}')
        
        trans = p.get_float(props, 'Transparency')
        if trans is not None and trans != 0:
            g.w(f'{var}.Transparency = {trans}')
        
        apply_mode = p.get_token(props, 'ApplyStrokeMode')
        if apply_mode is not None and apply_mode != 0:
            g.w(f'{var}.ApplyStrokeMode = Enum.ApplyStrokeMode.{self.enum_val("ApplyStrokeMode", apply_mode)}')
        
        line_join = p.get_token(props, 'LineJoinMode')
        if line_join is not None and line_join != 0:
            g.w(f'{var}.LineJoinMode = Enum.LineJoinMode.{self.enum_val("LineJoinMode", line_join)}')
        
        g.w(f'{var}.Parent = {parent}')
    
    def write_ui_corner(self, var, props, parent):
        """Write UICorner component"""
        g = self.gen
        p = self.parser
        
        radius = p.get_udim(props, 'CornerRadius')
        if radius:
            g.w(f'{var}.CornerRadius = {g.fmt_udim(radius)}')
        
        g.w(f'{var}.Parent = {parent}')
    
    def write_ui_list_layout(self, var, props, parent):
        """Write UIListLayout component"""
        g = self.gen
        p = self.parser
        
        fill_dir = p.get_token(props, 'FillDirection')
        if fill_dir is not None and fill_dir != 0:
            g.w(f'{var}.FillDirection = Enum.FillDirection.{self.enum_val("FillDirection", fill_dir)}')
        
        h_align = p.get_token(props, 'HorizontalAlignment')
        if h_align is not None and h_align != 0:
            g.w(f'{var}.HorizontalAlignment = Enum.HorizontalAlignment.{self.enum_val("HorizontalAlignment", h_align)}')
        
        v_align = p.get_token(props, 'VerticalAlignment')
        if v_align is not None and v_align != 0:
            g.w(f'{var}.VerticalAlignment = Enum.VerticalAlignment.{self.enum_val("VerticalAlignment", v_align)}')
        
        sort = p.get_token(props, 'SortOrder')
        if sort is not None:
            g.w(f'{var}.SortOrder = Enum.SortOrder.{self.enum_val("SortOrder", sort)}')
        
        padding = p.get_udim(props, 'Padding')
        if padding:
            g.w(f'{var}.Padding = {g.fmt_udim(padding)}')
        
        g.w(f'{var}.Parent = {parent}')
    
    def write_ui_grid_layout(self, var, props, parent):
        """Write UIGridLayout component"""
        g = self.gen
        p = self.parser
        
        cell_size = p.get_udim2(props, 'CellSize')
        if cell_size:
            g.w(f'{var}.CellSize = {g.fmt_udim2(cell_size)}')
        
        cell_padding = p.get_udim2(props, 'CellPadding')
        if cell_padding:
            g.w(f'{var}.CellPadding = {g.fmt_udim2(cell_padding)}')
        
        sort = p.get_token(props, 'SortOrder')
        if sort is not None:
            g.w(f'{var}.SortOrder = Enum.SortOrder.{self.enum_val("SortOrder", sort)}')
        
        fill_dir = p.get_token(props, 'FillDirection')
        if fill_dir is not None and fill_dir != 0:
            g.w(f'{var}.FillDirection = Enum.FillDirection.{self.enum_val("FillDirection", fill_dir)}')
        
        start_corner = p.get_token(props, 'StartCorner')
        if start_corner is not None and start_corner != 0:
            g.w(f'{var}.StartCorner = Enum.StartCorner.{self.enum_val("StartCorner", start_corner)}')
        
        g.w(f'{var}.Parent = {parent}')
    
    def write_ui_padding(self, var, props, parent):
        """Write UIPadding component"""
        g = self.gen
        p = self.parser
        
        for side in ['Left', 'Right', 'Top', 'Bottom']:
            pad = p.get_udim(props, f'Padding{side}')
            if pad:
                g.w(f'{var}.Padding{side} = {g.fmt_udim(pad)}')
        
        g.w(f'{var}.Parent = {parent}')
    
    def write_element(self, item, parent_var):
        """Write any element and its children recursively"""
        cls = item.get('class')
        if not cls:
            return
        
        props = item.find('Properties')
        name = self.parser.get_string(props, 'Name') if props else None
        var = self.gen.make_var_name(name, cls)
        
        self.gen.w(f"local {var} = Instance.new('{cls}')")
        
        # Write element based on class
        if cls == 'Frame':
            self.write_frame(var, props, parent_var)
        elif cls in ['TextLabel', 'TextButton', 'TextBox']:
            self.write_text_element(var, props, parent_var, cls)
        elif cls in ['ImageLabel', 'ImageButton']:
            self.write_image_element(var, props, parent_var, cls)
        elif cls == 'ScrollingFrame':
            self.write_scrolling_frame(var, props, parent_var)
        elif cls == 'UIStroke':
            self.write_ui_stroke(var, props, parent_var)
        elif cls == 'UICorner':
            self.write_ui_corner(var, props, parent_var)
        elif cls == 'UIListLayout':
            self.write_ui_list_layout(var, props, parent_var)
        elif cls == 'UIGridLayout':
            self.write_ui_grid_layout(var, props, parent_var)
        elif cls == 'UIPadding':
            self.write_ui_padding(var, props, parent_var)
        else:
            # Generic fallback
            if props:
                n = self.parser.get_string(props, 'Name')
                if n:
                    self.gen.w(f'{var}.Name = "{self.gen.escape_string(n)}"')
            self.gen.w(f'{var}.Parent = {parent_var}')
        
        self.gen.w('')
        
        # Process children
        for child in item.findall('Item'):
            self.write_element(child, var)
    
    def convert(self, xml_str):
        """Main conversion method"""
        try:
            root = ET.fromstring(xml_str)
        except ET.ParseError as e:
            return f'-- XML Parse Error: {e}'
        
        scale = self.config.get('scale', 1.0)
        self.gen = LuaCodeGenerator(scale)
        self.zindex = 0
        g = self.gen
        
        # Find all top-level items
        items = root.findall('Item')
        if not items:
            for child in root:
                items.extend(child.findall('Item'))
        
        if not items:
            return "-- Error: No GUI elements found in XML"
        
        # Calculate bounds for main container sizing
        min_x, min_y = float('inf'), float('inf')
        max_x, max_y = float('-inf'), float('-inf')
        
        for item in items:
            props = item.find('Properties')
            if props is None:
                continue
            pos = self.parser.get_udim2(props, 'Position')
            size = self.parser.get_udim2(props, 'Size')
            if pos and size:
                min_x = min(min_x, pos['xo'])
                min_y = min(min_y, pos['yo'])
                max_x = max(max_x, pos['xo'] + size['xo'])
                max_y = max(max_y, pos['yo'] + size['yo'])
        
        width = int((max_x - min_x) * scale) if min_x != float('inf') else 400
        height = int((max_y - min_y) * scale) if min_y != float('inf') else 300
        
        gui_name = self.config.get('gui_name', 'ConvertedGui')
        
        # Write header - matching the target style exactly
        g.w("local Players = game:GetService('Players')")
        g.w("local player = Players.LocalPlayer")
        g.w("local playerGui = player:WaitForChild('PlayerGui')")
        g.w("")
        g.w("local screenGui = Instance.new('ScreenGui')")
        g.w(f"screenGui.Name = '{gui_name}'")
        g.w("screenGui.ResetOnSpawn = false")
        g.w("screenGui.ZIndexBehavior = Enum.ZIndexBehavior.Sibling")
        g.w("screenGui.Parent = playerGui")
        g.w("")
        
        # Create main container frame
        g.w("local main = Instance.new('Frame')")
        g.w("main.Name = 'Main'")
        g.w(f"main.Size = UDim2.new(0, {width}, 0, {height})")
        
        # Position based on config
        pos = self.config.get('position', 'center')
        positions = {
            'center': ("UDim2.new(0.5, 0, 0.5, 0)", "Vector2.new(0.5, 0.5)"),
            'top': ("UDim2.new(0.5, 0, 0, 10)", "Vector2.new(0.5, 0)"),
            'bottom': ("UDim2.new(0.5, 0, 1, -10)", "Vector2.new(0.5, 1)"),
            'left': ("UDim2.new(0, 10, 0.5, 0)", "Vector2.new(0, 0.5)"),
            'right': ("UDim2.new(1, -10, 0.5, 0)", "Vector2.new(1, 0.5)"),
            'topleft': ("UDim2.new(0, 10, 0, 10)", "Vector2.new(0, 0)"),
            'topright': ("UDim2.new(1, -10, 0, 10)", "Vector2.new(1, 0)"),
            'bottomleft': ("UDim2.new(0, 10, 1, -10)", "Vector2.new(0, 1)"),
            'bottomright': ("UDim2.new(1, -10, 1, -10)", "Vector2.new(1, 1)"),
        }
        
        if pos in positions:
            g.w(f"main.Position = {positions[pos][0]}")
            g.w(f"main.AnchorPoint = {positions[pos][1]}")
        else:
            g.w("main.Position = UDim2.new(0, 0, 0, 0)")
        
        g.w("main.BackgroundTransparency = 1")
        g.w("main.BorderSizePixel = 0")
        g.w("main.Parent = screenGui")
        g.w("")
        
        # Process all elements
        for item in items:
            self.write_element(item, 'main')
        
        # Add draggable functionality if requested
        if self.config.get('draggable'):
            g.w("-- Draggable functionality")
            g.w("local UIS = game:GetService('UserInputService')")
            g.w("local dragging, dragInput, dragStart, startPos")
            g.w("")
            g.w("main.InputBegan:Connect(function(input)")
            g.w("\tif input.UserInputType == Enum.UserInputType.MouseButton1 or input.UserInputType == Enum.UserInputType.Touch then")
            g.w("\t\tdragging = true")
            g.w("\t\tdragStart = input.Position")
            g.w("\t\tstartPos = main.Position")
            g.w("\t\tinput.Changed:Connect(function()")
            g.w("\t\t\tif input.UserInputState == Enum.UserInputState.End then")
            g.w("\t\t\t\tdragging = false")
            g.w("\t\t\tend")
            g.w("\t\tend)")
            g.w("\tend")
            g.w("end)")
            g.w("")
            g.w("main.InputChanged:Connect(function(input)")
            g.w("\tif input.UserInputType == Enum.UserInputType.MouseMovement or input.UserInputType == Enum.UserInputType.Touch then")
            g.w("\t\tdragInput = input")
            g.w("\tend")
            g.w("end)")
            g.w("")
            g.w("UIS.InputChanged:Connect(function(input)")
            g.w("\tif input == dragInput and dragging then")
            g.w("\t\tlocal delta = input.Position - dragStart")
            g.w("\t\tmain.Position = UDim2.new(startPos.X.Scale, startPos.X.Offset + delta.X, startPos.Y.Scale, startPos.Y.Offset + delta.Y)")
            g.w("\tend")
            g.w("end)")
            g.w("")
        
        # Add destroy key if requested
        destroy_key = self.config.get('destroykey', 'none')
        key_map = {
            'x': 'X', 'delete': 'Delete', 'backspace': 'Backspace',
            'escape': 'Escape', 'p': 'P', 'm': 'M', 'k': 'K',
            'f1': 'F1', 'f2': 'F2', 'f3': 'F3', 'f4': 'F4'
        }
        
        if destroy_key in key_map:
            g.w("-- Destroy key binding")
            g.w("game:GetService('UserInputService').InputBegan:Connect(function(input, gameProcessed)")
            g.w(f"\tif not gameProcessed and input.KeyCode == Enum.KeyCode.{key_map[destroy_key]} then")
            g.w("\t\tscreenGui:Destroy()")
            g.w("\tend")
            g.w("end)")
        
        return g.get_output()


# Create converter instance
converter = UniversalConverter()


@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    print(f'Bot is in {len(bot.guilds)} guilds')


@bot.command(name='convert')
async def convert_cmd(ctx, drag='false', pos='center', scl: float = 1.0, key='none', *, name='ConvertedGui'):
    """Convert RBXMX file to Lua code"""
    if not ctx.message.attachments:
        await ctx.send("❌ Please attach an .rbxmx file!")
        return

    att = ctx.message.attachments[0]
    if not att.filename.lower().endswith('.rbxmx'):
        await ctx.send("❌ Please use an .rbxmx file!")
        return

    try:
        processing_msg = await ctx.send("⏳ Processing your file...")

        data = await att.read()
        xml_content = data.decode('utf-8')

        # Parse configuration
        draggable = drag.lower() == 'true'
        valid_positions = ['center', 'top', 'bottom', 'left', 'right', 
                          'topleft', 'topright', 'bottomleft', 'bottomright']
        position = pos.lower() if pos.lower() in valid_positions else 'center'
        scale = max(0.1, min(5.0, scl))
        valid_keys = ['none', 'x', 'delete', 'backspace', 'escape', 'p', 'm', 'k', 'f1', 'f2', 'f3', 'f4']
        destroy_key = key.lower() if key.lower() in valid_keys else 'none'
        gui_name = name.replace('_', ' ')

        # Configure and convert
        converter.set_config(
            draggable=draggable,
            position=position,
            scale=scale,
            destroykey=destroy_key,
            gui_name=gui_name
        )

        lua_code = converter.convert(xml_content)

        # Create output file
        output_filename = att.filename.replace('.rbxmx', '.lua')
        file = discord.File(io.BytesIO(lua_code.encode('utf-8')), filename=output_filename)

        # Create embed
        embed = discord.Embed(title="✅ Conversion Complete!", color=0x00ff00)
        embed.add_field(name="GUI Name", value=gui_name, inline=True)
        embed.add_field(name="Position", value=position, inline=True)
        embed.add_field(name="Scale", value=f"{scale}x", inline=True)
        embed.add_field(name="Draggable", value="Yes" if draggable else "No", inline=True)
        embed.add_field(name="Destroy Key", value=destroy_key.upper() if destroy_key != 'none' else "None", inline=True)
        embed.set_footer(text=f"Original file: {att.filename}")

        await processing_msg.delete()
        await ctx.send(embed=embed, file=file)

    except UnicodeDecodeError:
        await ctx.send("❌ Error: Could not decode file. Make sure it's a valid RBXMX file.")
    except Exception as e:
        await ctx.send(f"❌ Error during conversion: {str(e)}")


@bot.command(name='chelp')
async def chelp_cmd(ctx):
    """Show help information"""
    embed = discord.Embed(
        title="🔧 Figma to Lua Converter - Help",
        description="Convert Roblox GUI files (.rbxmx) to Lua scripts",
        color=0x5865F2
    )
    embed.add_field(
        name="📝 Commands",
        value="`!convert` - Convert an RBXMX file to Lua\n`!cconfig` - Show configuration options\n`!example` - Show usage examples\n`!ping` - Check bot latency",
        inline=False
    )
    embed.add_field(
        name="📎 How to Use",
        value="1. Export your GUI from Roblox as .rbxmx\n2. Attach the file to your message\n3. Use `!convert` with your options",
        inline=False
    )
    await ctx.send(embed=embed)


@bot.command(name='cconfig')
async def cconfig_cmd(ctx):
    """Show configuration options"""
    embed = discord.Embed(title="⚙️ Configuration Options", color=0x5865F2)
    embed.add_field(name="Usage", value="`!convert [drag] [position] [scale] [key] [name]`", inline=False)
    embed.add_field(name="drag", value="`true` / `false` (default: false)", inline=True)
    embed.add_field(name="position", value="`center`, `top`, `bottom`, `left`, `right`, `topleft`, `topright`, `bottomleft`, `bottomright`", inline=True)
    embed.add_field(name="scale", value="`0.1` to `5.0` (default: 1.0)", inline=True)
    embed.add_field(name="key", value="`none`, `x`, `delete`, `backspace`, `escape`, `p`, `m`, `k`, `f1`-`f4`", inline=True)
    embed.add_field(name="name", value="GUI name (use `_` for spaces)", inline=True)
    await ctx.send(embed=embed)


@bot.command(name='ping')
async def ping_cmd(ctx):
    """Check bot latency"""
    latency = round(bot.latency * 1000)
    await ctx.send(f"🏓 Pong! Latency: **{latency}ms**")


@bot.command(name='example')
async def example_cmd(ctx):
    """Show usage examples"""
    embed = discord.Embed(title="📚 Usage Examples", color=0x5865F2)
    embed.add_field(name="Basic", value="`!convert`", inline=False)
    embed.add_field(name="Draggable", value="`!convert true`", inline=False)
    embed.add_field(name="Custom Position", value="`!convert false topleft`", inline=False)
    embed.add_field(name="Scaled", value="`!convert true center 1.5`", inline=False)
    embed.add_field(name="With Close Key", value="`!convert true center 1.0 escape`", inline=False)
    embed.add_field(name="Full Example", value="`!convert true center 1.2 x My_Cool_GUI`", inline=False)
    await ctx.send(embed=embed)

        # Calculate bounds
        min_x, min_y = float('inf'), float('inf')
        max_x, max_y = float('-inf'), float('-inf')
        
        for item in items:
            props = item.find('Properties')
            if props is None:
                continue
            pos = self.parser.get_udim2(props, 'Position')
            size = self.parser.get_udim2(props, 'Size')
            if pos and size:
                min_x = min(min_x, pos['xo'])
                min_y = min(min_y, pos['yo'])
                max_x = max(max_x, pos['xo'] + size['xo'])
                max_y = max(max_y, pos['yo'] + size['yo'])
        
        width = int((max_x - min_x) * scale) if min_x != float('inf') else 400
        height = int((max_y - min_y) * scale) if min_y != float('inf') else 300
        
        gui_name = self.config.get('gui_name', 'ConvertedGui')
        
        # Write header - matching the target style exactly
        g.w("local Players = game:GetService('Players')")
        g.w("local player = Players.LocalPlayer")
        g.w("local playerGui = player:WaitForChild('PlayerGui')")
        g.w("")
        g.w("local screenGui = Instance.new('ScreenGui')")
        g.w(f"screenGui.Name = '{gui_name}'")
        g.w("screenGui.ResetOnSpawn = false")
        g.w("screenGui.ZIndexBehavior = Enum.ZIndexBehavior.Sibling")
        g.w("screenGui.Parent = playerGui")
        g.w("")

        async def main():
    await start_web_server()
    token = os.getenv('DISCORD_BOT_TOKEN')
    if token:
        await bot.start(token)
    else:
        print("❌ No DISCORD_BOT_TOKEN found!")


if __name__ == "__main__":
    if os.getenv('DISCORD_BOT_TOKEN'):
        asyncio.run(main())
    else:
        print("❌ No DISCORD_BOT_TOKEN environment variable set!")
