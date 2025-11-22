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

class UniversalConverter:
    def __init__(self):
        self.lines = []
        self.config = {}
        self.scale = 1.0
        self.var_counter = 0
        self.name_to_var = {}
        
        self.enums = {
            'ApplyStrokeMode': {0: 'Contextual', 1: 'Border'},
            'LineJoinMode': {0: 'Round', 1: 'Bevel', 2: 'Miter'},
            'TextXAlignment': {0: 'Center', 1: 'Left', 2: 'Right'},
            'TextYAlignment': {0: 'Center', 1: 'Top', 2: 'Bottom'},
            'AutomaticSize': {0: 'None', 1: 'X', 2: 'Y', 3: 'XY'},
            'ScaleType': {0: 'Stretch', 1: 'Slice', 2: 'Tile', 3: 'Fit', 4: 'Crop'},
            'FillDirection': {0: 'Horizontal', 1: 'Vertical'},
            'HorizontalAlignment': {0: 'Center', 1: 'Left', 2: 'Right'},
            'VerticalAlignment': {0: 'Center', 1: 'Top', 2: 'Bottom'},
            'SortOrder': {0: 'Name', 1: 'Custom', 2: 'LayoutOrder'},
            'ResamplerMode': {0: 'Default', 1: 'Pixelated'},
            'BorderMode': {0: 'Outline', 1: 'Middle', 2: 'Inset'},
            'FontWeight': {100: 'Thin', 200: 'ExtraLight', 300: 'Light', 400: 'Regular', 
                          500: 'Medium', 600: 'SemiBold', 700: 'Bold', 800: 'ExtraBold', 900: 'Heavy'},
            'FontStyle': {'Normal': 'Normal', 'Italic': 'Italic'},
            'ZIndexBehavior': {0: 'Global', 1: 'Sibling'},
            'StartCorner': {0: 'TopLeft', 1: 'TopRight', 2: 'BottomLeft', 3: 'BottomRight'},
        }
        
        self.ui_components = {
            'UIStroke', 'UICorner', 'UIGradient', 'UIListLayout', 'UIGridLayout', 
            'UIPadding', 'UIAspectRatioConstraint', 'UISizeConstraint', 'UIScale', 
            'UITextSizeConstraint', 'UIFlexItem', 'UITableLayout', 'UIPageLayout'
        }
        
        self.gui_elements = {
            'Frame', 'TextLabel', 'TextButton', 'TextBox', 'ImageLabel', 
            'ImageButton', 'ScrollingFrame', 'ViewportFrame', 'VideoFrame',
            'CanvasGroup'
        }

    def set_config(self, **kw):
        self.config = kw
        self.scale = kw.get('scale', 1.0)

    def w(self, line):
        self.lines.append(line)

    def get_var_name(self, name, cls):
        """Generate a clean variable name"""
        self.var_counter += 1
        if name:
            clean = re.sub(r'[^a-zA-Z0-9]', '', name)
            if clean and not clean[0].isdigit():
                return f"{clean.lower()}_{self.var_counter}"
        return f"{cls.lower()}_{self.var_counter}"

    def get_prop(self, props, name, tag):
        """Generic property getter"""
        if props is None:
            return None
        for p in props:
            if p.get('name') == name and p.tag == tag:
                return p
        return None

    def get_udim2(self, props, name):
        p = self.get_prop(props, name, 'UDim2')
        if p is not None:
            return {
                'xs': float(p.findtext('XS') or 0),
                'xo': float(p.findtext('XO') or 0),
                'ys': float(p.findtext('YS') or 0),
                'yo': float(p.findtext('YO') or 0)
            }
        return None

    def get_udim(self, props, name):
        p = self.get_prop(props, name, 'UDim')
        if p is not None:
            return {
                's': float(p.findtext('S') or 0),
                'o': float(p.findtext('O') or 0)
            }
        return None

    def get_color3(self, props, name):
        p = self.get_prop(props, name, 'Color3')
        if p is not None:
            return {
                'r': float(p.findtext('R') or 0),
                'g': float(p.findtext('G') or 0),
                'b': float(p.findtext('B') or 0)
            }
        return None

    def get_color3uint8(self, props, name):
        """Handle Color3uint8 format"""
        p = self.get_prop(props, name, 'Color3uint8')
        if p is not None and p.text:
            val = int(p.text)
            r = ((val >> 16) & 0xFF) / 255
            g = ((val >> 8) & 0xFF) / 255
            b = (val & 0xFF) / 255
            return {'r': r, 'g': g, 'b': b}
        return None

    def get_any_color3(self, props, name):
        """Get color from either Color3 or Color3uint8"""
        return self.get_color3(props, name) or self.get_color3uint8(props, name)

    def get_str(self, props, name):
        p = self.get_prop(props, name, 'string')
        if p is not None:
            return p.text or ''
        return None

    def get_float(self, props, name):
        p = self.get_prop(props, name, 'float')
        if p is not None:
            return float(p.text or 0)
        p = self.get_prop(props, name, 'double')
        if p is not None:
            return float(p.text or 0)
        return None

    def get_int(self, props, name):
        p = self.get_prop(props, name, 'int')
        if p is not None:
            return int(p.text or 0)
        p = self.get_prop(props, name, 'int64')
        if p is not None:
            return int(p.text or 0)
        return None

    def get_bool(self, props, name):
        p = self.get_prop(props, name, 'bool')
        if p is not None:
            return p.text == 'true'
        return None

    def get_token(self, props, name):
        p = self.get_prop(props, name, 'token')
        if p is not None:
            return int(p.text or 0)
        return None

    def get_vector2(self, props, name):
        p = self.get_prop(props, name, 'Vector2')
        if p is not None:
            return {
                'x': float(p.findtext('X') or 0),
                'y': float(p.findtext('Y') or 0)
            }
        return None

    def get_font(self, props, name):
        p = self.get_prop(props, name, 'Font')
        if p is not None:
            fam = p.find('Family')
            url = 'rbxasset://fonts/families/SourceSansPro.json'
            if fam is not None:
                u = fam.find('url')
                if u is not None and u.text:
                    url = u.text
            wgt = p.findtext('Weight') or '400'
            sty = p.findtext('Style') or 'Normal'
            return {'url': url, 'weight': int(wgt), 'style': sty}
        return None

    def get_content(self, props, name):
        p = self.get_prop(props, name, 'Content')
        if p is not None:
            u = p.find('url')
            if u is not None and u.text and u.text not in ['undefined', 'null', '']:
                return u.text
        return None

    def get_colorsequence(self, props, name):
        """Parse ColorSequence for gradients"""
        p = self.get_prop(props, name, 'ColorSequence')
        if p is None:
            return None
        keypoints = []
        for kp in p.findall('Keypoint'):
            time = float(kp.get('time', 0))
            color_elem = kp.find('Color')
            if color_elem is not None:
                r = float(color_elem.findtext('R') or 0)
                g = float(color_elem.findtext('G') or 0)
                b = float(color_elem.findtext('B') or 0)
                keypoints.append({'time': time, 'r': r, 'g': g, 'b': b})
        return keypoints if keypoints else None

    def get_numbersequence(self, props, name):
        """Parse NumberSequence for gradients"""
        p = self.get_prop(props, name, 'NumberSequence')
        if p is None:
            return None
        keypoints = []
        for kp in p.findall('Keypoint'):
            time = float(kp.get('time', 0))
            value = float(kp.get('value', 0))
            envelope = float(kp.get('envelope', 0))
            keypoints.append({'time': time, 'value': value, 'envelope': envelope})
        return keypoints if keypoints else None

    def enum_str(self, enum_type, val):
        mapping = self.enums.get(enum_type, {})
        enum_val = mapping.get(val, str(val))
        return f"Enum.{enum_type}.{enum_val}"

    def scale_offset(self, offset):
        """Apply scale to pixel offsets"""
        return int(offset * self.scale)

    def format_udim2(self, udim2, scale_offsets=True):
        xs, xo, ys, yo = udim2['xs'], udim2['xo'], udim2['ys'], udim2['yo']
        if scale_offsets:
            xo = self.scale_offset(xo)
            yo = self.scale_offset(yo)
        else:
            xo = int(xo)
            yo = int(yo)
        return f"UDim2.new({xs}, {xo}, {ys}, {yo})"

    def format_udim(self, udim, scale_offset=True):
        s, o = udim['s'], udim['o']
        if scale_offset:
            o = self.scale_offset(o)
        else:
            o = int(o)
        return f"UDim.new({s}, {o})"

    def format_color3(self, color):
        return f"Color3.new({color['r']}, {color['g']}, {color['b']})"

    def format_vector2(self, vec):
        return f"Vector2.new({vec['x']}, {vec['y']})"

    def escape_str(self, s):
        if s is None:
            return ""
        return s.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\r', '')

    def write_common_props(self, var, props, cls, zindex):
        """Write properties common to all GUI elements"""
        name = self.get_str(props, 'Name')
        if name:
            self.w(f'{var}.Name = "{self.escape_str(name)}"')

        if cls not in self.ui_components:
            size = self.get_udim2(props, 'Size')
            if size:
                self.w(f"{var}.Size = {self.format_udim2(size)}")

            pos = self.get_udim2(props, 'Position')
            if pos:
                self.w(f"{var}.Position = {self.format_udim2(pos)}")

            anchor = self.get_vector2(props, 'AnchorPoint')
            if anchor:
                self.w(f"{var}.AnchorPoint = {self.format_vector2(anchor)}")

            rotation = self.get_float(props, 'Rotation')
            if rotation is not None and rotation != 0:
                self.w(f"{var}.Rotation = {rotation}")

            self.w(f"{var}.ZIndex = {zindex}")

        bg_color = self.get_any_color3(props, 'BackgroundColor3')
        if bg_color:
            self.w(f"{var}.BackgroundColor3 = {self.format_color3(bg_color)}")

        bg_trans = self.get_float(props, 'BackgroundTransparency')
        if bg_trans is not None:
            self.w(f"{var}.BackgroundTransparency = {bg_trans}")

        border = self.get_int(props, 'BorderSizePixel')
        if border is not None:
            self.w(f"{var}.BorderSizePixel = {border}")

        border_color = self.get_any_color3(props, 'BorderColor3')
        if border_color and (border is None or border > 0):
            self.w(f"{var}.BorderColor3 = {self.format_color3(border_color)}")

        visible = self.get_bool(props, 'Visible')
        if visible is not None and not visible:
            self.w(f"{var}.Visible = false")

        clip = self.get_bool(props, 'ClipsDescendants')
        if clip is not None and clip:
            self.w(f"{var}.ClipsDescendants = true")

        auto_size = self.get_token(props, 'AutomaticSize')
        if auto_size is not None and auto_size != 0:
            self.w(f"{var}.AutomaticSize = {self.enum_str('AutomaticSize', auto_size)}")

        layout_order = self.get_int(props, 'LayoutOrder')
        if layout_order is not None and layout_order != 0:
            self.w(f"{var}.LayoutOrder = {layout_order}")

    def write_text_props(self, var, props):
        """Write text-specific properties"""
        text = self.get_str(props, 'Text')
        if text is not None:
            self.w(f'{var}.Text = "{self.escape_str(text)}"')

        text_color = self.get_any_color3(props, 'TextColor3')
        if text_color:
            self.w(f"{var}.TextColor3 = {self.format_color3(text_color)}")

        text_trans = self.get_float(props, 'TextTransparency')
        if text_trans is not None and text_trans != 0:
            self.w(f"{var}.TextTransparency = {text_trans}")

        text_size = self.get_int(props, 'TextSize')
        if text_size is not None:
            self.w(f"{var}.TextSize = {self.scale_offset(text_size)}")

        text_scaled = self.get_bool(props, 'TextScaled')
        if text_scaled:
            self.w(f"{var}.TextScaled = true")

        text_wrapped = self.get_bool(props, 'TextWrapped')
        if text_wrapped:
            self.w(f"{var}.TextWrapped = true")

        text_x = self.get_token(props, 'TextXAlignment')
        if text_x is not None:
            self.w(f"{var}.TextXAlignment = {self.enum_str('TextXAlignment', text_x)}")

        text_y = self.get_token(props, 'TextYAlignment')
        if text_y is not None:
            self.w(f"{var}.TextYAlignment = {self.enum_str('TextYAlignment', text_y)}")

        rich_text = self.get_bool(props, 'RichText')
        if rich_text:
            self.w(f"{var}.RichText = true")

        font = self.get_font(props, 'FontFace')
        if font:
            weight = self.enums['FontWeight'].get(font['weight'], 'Regular')
            style = font['style']
            self.w(f'{var}.FontFace = Font.new("{font["url"]}", Enum.FontWeight.{weight}, Enum.FontStyle.{style})')

        max_visible = self.get_int(props, 'MaxVisibleGraphemes')
        if max_visible is not None and max_visible != -1:
            self.w(f"{var}.MaxVisibleGraphemes = {max_visible}")

        line_height = self.get_float(props, 'LineHeight')
        if line_height is not None and line_height != 1:
            self.w(f"{var}.LineHeight = {line_height}")

    def write_image_props(self, var, props):
        """Write image-specific properties"""
        image = self.get_content(props, 'Image')
        if image:
            self.w(f'{var}.Image = "{image}"')

        image_trans = self.get_float(props, 'ImageTransparency')
        if image_trans is not None and image_trans != 0:
            self.w(f"{var}.ImageTransparency = {image_trans}")

        image_color = self.get_any_color3(props, 'ImageColor3')
        if image_color:
            self.w(f"{var}.ImageColor3 = {self.format_color3(image_color)}")

        scale_type = self.get_token(props, 'ScaleType')
        if scale_type is not None and scale_type != 0:
            self.w(f"{var}.ScaleType = {self.enum_str('ScaleType', scale_type)}")

        slice_center = self.get_prop(props, 'SliceCenter', 'Rect')
        if slice_center is not None:
            min_x = int(float(slice_center.findtext('min/X') or 0))
            min_y = int(float(slice_center.findtext('min/Y') or 0))
            max_x = int(float(slice_center.findtext('max/X') or 0))
            max_y = int(float(slice_center.findtext('max/Y') or 0))
            self.w(f"{var}.SliceCenter = Rect.new({min_x}, {min_y}, {max_x}, {max_y})")

        slice_scale = self.get_float(props, 'SliceScale')
        if slice_scale is not None and slice_scale != 1:
            self.w(f"{var}.SliceScale = {slice_scale}")

        tile_size = self.get_udim2(props, 'TileSize')
        if tile_size:
            self.w(f"{var}.TileSize = {self.format_udim2(tile_size)}")

        resampler = self.get_token(props, 'ResamplerMode')
        if resampler is not None and resampler != 0:
            self.w(f"{var}.ResamplerMode = {self.enum_str('ResamplerMode', resampler)}")

    def write_scrolling_props(self, var, props):
        """Write scrolling frame specific properties"""
        canvas_size = self.get_udim2(props, 'CanvasSize')
        if canvas_size:
            self.w(f"{var}.CanvasSize = {self.format_udim2(canvas_size)}")

        canvas_pos = self.get_vector2(props, 'CanvasPosition')
        if canvas_pos:
            self.w(f"{var}.CanvasPosition = {self.format_vector2(canvas_pos)}")

        scroll_bar_thick = self.get_int(props, 'ScrollBarThickness')
        if scroll_bar_thick is not None:
            self.w(f"{var}.ScrollBarThickness = {self.scale_offset(scroll_bar_thick)}")

        scroll_bar_color = self.get_any_color3(props, 'ScrollBarImageColor3')
        if scroll_bar_color:
            self.w(f"{var}.ScrollBarImageColor3 = {self.format_color3(scroll_bar_color)}")

        scroll_bar_trans = self.get_float(props, 'ScrollBarImageTransparency')
        if scroll_bar_trans is not None:
            self.w(f"{var}.ScrollBarImageTransparency = {scroll_bar_trans}")

        elastic = self.get_token(props, 'ElasticBehavior')
        if elastic is not None:
            elastic_map = {0: 'WhenScrollable', 1: 'Always', 2: 'Never'}
            self.w(f"{var}.ElasticBehavior = Enum.ElasticBehavior.{elastic_map.get(elastic, 'WhenScrollable')}")

        scroll_enabled = self.get_bool(props, 'ScrollingEnabled')
        if scroll_enabled is not None and not scroll_enabled:
            self.w(f"{var}.ScrollingEnabled = false")

    def write_ui_stroke(self, var, props):
        """Write UIStroke properties"""
        color = self.get_any_color3(props, 'Color')
        if color:
            self.w(f"{var}.Color = {self.format_color3(color)}")

        trans = self.get_float(props, 'Transparency')
        if trans is not None and trans != 0:
            self.w(f"{var}.Transparency = {trans}")

        thickness = self.get_float(props, 'Thickness')
        if thickness is not None:
            self.w(f"{var}.Thickness = {thickness * self.scale}")

        apply_mode = self.get_token(props, 'ApplyStrokeMode')
        if apply_mode is not None:
            self.w(f"{var}.ApplyStrokeMode = {self.enum_str('ApplyStrokeMode', apply_mode)}")

        line_join = self.get_token(props, 'LineJoinMode')
        if line_join is not None:
            self.w(f"{var}.LineJoinMode = {self.enum_str('LineJoinMode', line_join)}")

        enabled = self.get_bool(props, 'Enabled')
        if enabled is not None and not enabled:
            self.w(f"{var}.Enabled = false")

    def write_ui_corner(self, var, props):
        """Write UICorner properties"""
        corner = self.get_udim(props, 'CornerRadius')
        if corner:
            self.w(f"{var}.CornerRadius = {self.format_udim(corner)}")

    def write_ui_gradient(self, var, props):
        """Write UIGradient properties"""
        color_seq = self.get_colorsequence(props, 'Color')
        if color_seq:
            keypoints = ', '.join([
                f"ColorSequenceKeypoint.new({kp['time']}, Color3.new({kp['r']}, {kp['g']}, {kp['b']}))"
                for kp in color_seq
            ])
            self.w(f"{var}.Color = ColorSequence.new({{{keypoints}}})")

        trans_seq = self.get_numbersequence(props, 'Transparency')
        if trans_seq:
            keypoints = ', '.join([
                f"NumberSequenceKeypoint.new({kp['time']}, {kp['value']})"
                for kp in trans_seq
            ])
            self.w(f"{var}.Transparency = NumberSequence.new({{{keypoints}}})")

        rotation = self.get_float(props, 'Rotation')
        if rotation is not None and rotation != 0:
            self.w(f"{var}.Rotation = {rotation}")

        offset = self.get_vector2(props, 'Offset')
        if offset:
            self.w(f"{var}.Offset = {self.format_vector2(offset)}")

        enabled = self.get_bool(props, 'Enabled')
        if enabled is not None and not enabled:
            self.w(f"{var}.Enabled = false")

    def write_ui_list_layout(self, var, props):
        """Write UIListLayout properties"""
        fill_dir = self.get_token(props, 'FillDirection')
        if fill_dir is not None:
            self.w(f"{var}.FillDirection = {self.enum_str('FillDirection', fill_dir)}")

        h_align = self.get_token(props, 'HorizontalAlignment')
        if h_align is not None:
            self.w(f"{var}.HorizontalAlignment = {self.enum_str('HorizontalAlignment', h_align)}")

        v_align = self.get_token(props, 'VerticalAlignment')
        if v_align is not None:
            self.w(f"{var}.VerticalAlignment = {self.enum_str('VerticalAlignment', v_align)}")

        sort_order = self.get_token(props, 'SortOrder')
        if sort_order is not None:
            self.w(f"{var}.SortOrder = {self.enum_str('SortOrder', sort_order)}")

        padding = self.get_udim(props, 'Padding')
        if padding:
            self.w(f"{var}.Padding = {self.format_udim(padding)}")

        wraps = self.get_bool(props, 'Wraps')
        if wraps:
            self.w(f"{var}.Wraps = true")

    def write_ui_grid_layout(self, var, props):
        """Write UIGridLayout properties"""
        cell_size = self.get_udim2(props, 'CellSize')
        if cell_size:
            self.w(f"{var}.CellSize = {self.format_udim2(cell_size)}")

        cell_padding = self.get_udim2(props, 'CellPadding')
        if cell_padding:
            self.w(f"{var}.CellPadding = {self.format_udim2(cell_padding)}")

        fill_dir = self.get_token(props, 'FillDirection')
        if fill_dir is not None:
            self.w(f"{var}.FillDirection = {self.enum_str('FillDirection', fill_dir)}")

        h_align = self.get_token(props, 'HorizontalAlignment')
        if h_align is not None:
            self.w(f"{var}.HorizontalAlignment = {self.enum_str('HorizontalAlignment', h_align)}")

        v_align = self.get_token(props, 'VerticalAlignment')
        if v_align is not None:
            self.w(f"{var}.VerticalAlignment = {self.enum_str('VerticalAlignment', v_align)}")

        sort_order = self.get_token(props, 'SortOrder')
        if sort_order is not None:
            self.w(f"{var}.SortOrder = {self.enum_str('SortOrder', sort_order)}")

        start_corner = self.get_token(props, 'StartCorner')
        if start_corner is not None:
            self.w(f"{var}.StartCorner = {self.enum_str('StartCorner', start_corner)}")

        rows = self.get_int(props, 'FillDirectionMaxCells')
        if rows is not None and rows != 0:
            self.w(f"{var}.FillDirectionMaxCells = {rows}")

    def write_ui_padding(self, var, props):
        """Write UIPadding properties"""
        for side in ['Left', 'Right', 'Top', 'Bottom']:
            padding = self.get_udim(props, f'Padding{side}')
            if padding:
                self.w(f"{var}.Padding{side} = {self.format_udim(padding)}")

    def write_ui_aspect_ratio(self, var, props):
        """Write UIAspectRatioConstraint properties"""
        ratio = self.get_float(props, 'AspectRatio')
        if ratio is not None:
            self.w(f"{var}.AspectRatio = {ratio}")

        aspect_type = self.get_token(props, 'AspectType')
        if aspect_type is not None:
            types = {0: 'FitWithinMaxSize', 1: 'ScaleWithParentSize'}
            self.w(f"{var}.AspectType = Enum.AspectType.{types.get(aspect_type, 'FitWithinMaxSize')}")

        dominant = self.get_token(props, 'DominantAxis')
        if dominant is not None:
            axes = {0: 'Width', 1: 'Height'}
            self.w(f"{var}.DominantAxis = Enum.DominantAxis.{axes.get(dominant, 'Width')}")

    def write_ui_size_constraint(self, var, props):
        """Write UISizeConstraint properties"""
        min_size = self.get_vector2(props, 'MinSize')
        if min_size:
            self.w(f"{var}.MinSize = Vector2.new({self.scale_offset(min_size['x'])}, {self.scale_offset(min_size['y'])})")

        max_size = self.get_vector2(props, 'MaxSize')
        if max_size:
            x = self.scale_offset(max_size['x']) if max_size['x'] < 1e9 else "math.huge"
            y = self.scale_offset(max_size['y']) if max_size['y'] < 1e9 else "math.huge"
            self.w(f"{var}.MaxSize = Vector2.new({x}, {y})")

    def write_ui_scale(self, var, props):
        """Write UIScale properties"""
        scale = self.get_float(props, 'Scale')
        if scale is not None:
            self.w(f"{var}.Scale = {scale}")

    def write_ui_text_size_constraint(self, var, props):
        """Write UITextSizeConstraint properties"""
        min_size = self.get_int(props, 'MinTextSize')
        if min_size is not None:
            self.w(f"{var}.MinTextSize = {self.scale_offset(min_size)}")

        max_size = self.get_int(props, 'MaxTextSize')
        if max_size is not None:
            self.w(f"{var}.MaxTextSize = {self.scale_offset(max_size)}")

    def write_element(self, item, parent_var, zindex_base):
        """Write a single element and its children"""
        cls = item.get('class')
        if not cls:
            return zindex_base

        props = item.find('Properties')
        name = self.get_str(props, 'Name') if props else None
        var = self.get_var_name(name, cls)

        self.w(f"local {var} = Instance.new('{cls}')")

        current_zindex = zindex_base + 1

        if props is not None:
            # Write class-specific properties
            if cls in self.gui_elements:
                self.write_common_props(var, props, cls, current_zindex)

            if cls in ['TextLabel', 'TextButton', 'TextBox']:
                self.write_text_props(var, props)

            if cls in ['ImageLabel', 'ImageButton']:
                self.write_image_props(var, props)

            if cls == 'ScrollingFrame':
                self.write_common_props(var, props, cls, current_zindex)
                self.write_scrolling_props(var, props)

            if cls == 'UIStroke':
                self.write_ui_stroke(var, props)

            if cls == 'UICorner':
                self.write_ui_corner(var, props)

            if cls == 'UIGradient':
                self.write_ui_gradient(var, props)

            if cls == 'UIListLayout':
                self.write_ui_list_layout(var, props)

            if cls == 'UIGridLayout':
                self.write_ui_grid_layout(var, props)

            if cls == 'UIPadding':
                self.write_ui_padding(var, props)

            if cls == 'UIAspectRatioConstraint':
                self.write_ui_aspect_ratio(var, props)

            if cls == 'UISizeConstraint':
                self.write_ui_size_constraint(var, props)

            if cls == 'UIScale':
                self.write_ui_scale(var, props)

            if cls == 'UITextSizeConstraint':
                self.write_ui_text_size_constraint(var, props)

            # Button-specific properties
            if cls in ['TextButton', 'ImageButton']:
                auto_btn_color = self.get_bool(props, 'AutoButtonColor')
                if auto_btn_color is not None and not auto_btn_color:
                    self.w(f"{var}.AutoButtonColor = false")

                modal = self.get_bool(props, 'Modal')
                if modal:
                    self.w(f"{var}.Modal = true")

            # TextBox-specific properties
            if cls == 'TextBox':
                placeholder = self.get_str(props, 'PlaceholderText')
                if placeholder:
                    self.w(f'{var}.PlaceholderText = "{self.escape_str(placeholder)}"')

                placeholder_color = self.get_any_color3(props, 'PlaceholderColor3')
                if placeholder_color:
                    self.w(f"{var}.PlaceholderColor3 = {self.format_color3(placeholder_color)}")

                clear_on_focus = self.get_bool(props, 'ClearTextOnFocus')
                if clear_on_focus is not None and not clear_on_focus:
                    self.w(f"{var}.ClearTextOnFocus = false")

                multi_line = self.get_bool(props, 'MultiLine')
                if multi_line:
                    self.w(f"{var}.MultiLine = true")

        self.w(f"{var}.Parent = {parent_var}")
        self.w("")

        # Process children
        child_zindex = current_zindex
        for child in item.findall('Item'):
            child_zindex = self.write_element(child, var, child_zindex)

        return child_zindex

    def convert(self, xml_str):
        """Convert RBXMX XML to Lua code"""
        try:
            root = ET.fromstring(xml_str)
        except ET.ParseError as e:
            return f'-- XML Parse Error: {e}'

        self.lines = []
        self.var_counter = 0
        self.name_to_var = {}

        gui_name = self.config.get('gui_name', 'ConvertedGui')
        
        # Write header
        self.w("local Players = game:GetService('Players')")
        self.w("local player = Players.LocalPlayer")
        self.w("local playerGui = player:WaitForChild('PlayerGui')")
        self.w("")
        self.w("local screenGui = Instance.new('ScreenGui')")
        self.w(f"screenGui.Name = '{gui_name}'")
        self.w("screenGui.ResetOnSpawn = false")
        self.w("screenGui.ZIndexBehavior = Enum.ZIndexBehavior.Sibling")
        self.w("screenGui.Parent = playerGui")
        self.w("")

        # Find all top-level items and calculate bounds
        items = root.findall('Item')
        
        if not items:
            # Try nested structure
            for child in root:
                if child.tag == 'Item':
                    items = [child]
                    break
                items.extend(child.findall('Item'))

        if not items:
            return "-- No GUI elements found in XML"

        # Calculate bounds for positioning
        min_x, min_y = float('inf'), float('inf')
        max_x, max_y = float('-inf'), float('-inf')
        
        for item in items:
            props = item.find('Properties')
            if props is None:
                continue
            pos = self.get_udim2(props, 'Position')
            size = self.get_udim2(props, 'Size')
            if pos and size:
                x, y = pos['xo'], pos['yo']
                w, h = size['xo'], size['yo']
                min_x = min(min_x, x)
                min_y = min(min_y, y)
                max_x = max(max_x, x + w)
                max_y = max(max_y, y + h)

        if min_x == float('inf'):
            width, height = 400, 300
        else:
            width = max_x - min_x
            height = max_y - min_y

        scaled_width = self.scale_offset(width)
        scaled_height = self.scale_offset(height)

        # Create main container
        self.w("local main = Instance.new('Frame')")
        self.w("main.Name = 'Main'")
        self.w(f"main.Size = UDim2.new(0, {scaled_width}, 0, {scaled_height})")

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
            self.w(f"main.Position = {positions[pos][0]}")
            self.w(f"main.AnchorPoint = {positions[pos][1]}")
        else:
            self.w("main.Position = UDim2.new(0, 0, 0, 0)")

        self.w("main.BackgroundTransparency = 1")
        self.w("main.BorderSizePixel = 0")
        self.w("main.Parent = screenGui")
        self.w("")

        # Process all elements
        zindex = 0
        for item in items:
            zindex = self.write_element(item, 'main', zindex)

        # Add draggable functionality if requested
        if self.config.get('draggable'):
            self.w("-- Draggable functionality")
            self.w("local UIS = game:GetService('UserInputService')")
            self.w("local dragging, dragInput, dragStart, startPos")
            self.w("")
            self.w("main.InputBegan:Connect(function(input)")
            self.w("\tif input.UserInputType == Enum.UserInputType.MouseButton1 or input.UserInputType == Enum.UserInputType.Touch then")
            self.w("\t\tdragging = true")
            self.w("\t\tdragStart = input.Position")
            self.w("\t\tstartPos = main.Position")
            self.w("\t\tinput.Changed:Connect(function()")
            self.w("\t\t\tif input.UserInputState == Enum.UserInputState.End then")
            self.w("\t\t\t\tdragging = false")
            self.w("\t\t\tend")
            self.w("\t\tend)")
            self.w("\tend")
            self.w("end)")
            self.w("")
            self.w("main.InputChanged:Connect(function(input)")
            self.w("\tif input.UserInputType == Enum.UserInputType.MouseMovement or input.UserInputType == Enum.UserInputType.Touch then")
            self.w("\t\tdragInput = input")
            self.w("\tend")
            self.w("end)")
            self.w("")
            self.w("UIS.InputChanged:Connect(function(input)")
            self.w("\tif input == dragInput and dragging then")
            self.w("\t\tlocal delta = input.Position - dragStart")
            self.w("\t\tmain.Position = UDim2.new(startPos.X.Scale, startPos.X.Offset + delta.X, startPos.Y.Scale, startPos.Y.Offset + delta.Y)")
            self.w("\tend")
            self.w("end)")
            self.w("")

        # Add destroy key if requested
        destroy_key = self.config.get('destroykey', 'none')
        key_map = {
            'x': 'X', 'delete': 'Delete', 'backspace': 'Backspace',
            'escape': 'Escape', 'p': 'P', 'm': 'M', 'k': 'K',
            'f1': 'F1', 'f2': 'F2', 'f3': 'F3', 'f4': 'F4'
        }
        
        if destroy_key in key_map:
            self.w("-- Destroy key binding")
            self.w("game:GetService('UserInputService').InputBegan:Connect(function(input, gameProcessed)")
            self.w("\tif not gameProcessed and input.KeyCode == Enum.KeyCode." + key_map[destroy_key] + " then")
            self.w("\t\tscreenGui:Destroy()")
            self.w("\tend")
            self.w("end)")
            self.w("")

        # Return statement
        self.w("return screenGui")

        return '\n'.join(self.lines)


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
        # Send processing message
        processing_msg = await ctx.send("⏳ Processing your file...")

        # Read and decode the file
        data = await att.read()
        xml_content = data.decode('utf-8')

        # Parse configuration
        draggable = drag.lower() == 'true'
        valid_positions = ['center', 'top', 'bottom', 'left', 'right', 
                          'topleft', 'topright', 'bottomleft', 'bottomright', 'original']
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
        file = discord.File(
            io.BytesIO(lua_code.encode('utf-8')),
            filename=output_filename
        )

        # Create embed with conversion info
        embed = discord.Embed(
            title="✅ Conversion Complete!",
            color=0x00ff00
        )
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
        value="""
`!convert` - Convert an RBXMX file to Lua
`!cconfig` - Show configuration options
`!example` - Show usage examples
`!ping` - Check bot latency
`!chelp` - Show this help message
        """,
        inline=False
    )
    embed.add_field(
        name="📎 How to Use",
        value="1. Export your GUI from Roblox as .rbxmx\n2. Attach the file to your message\n3. Use `!convert` with your options",
        inline=False
    )
    embed.set_footer(text="Use !cconfig for detailed configuration options")
    await ctx.send(embed=embed)


@bot.command(name='cconfig')
async def cconfig_cmd(ctx):
    """Show configuration options"""
    embed = discord.Embed(
        title="⚙️ Configuration Options",
        color=0x5865F2
    )
    embed.add_field(
        name="Usage",
        value="`!convert [drag] [position] [scale] [key] [name]`",
        inline=False
    )
    embed.add_field(
        name="drag",
        value="Make GUI draggable\n`true` / `false`\nDefault: `false`",
        inline=True
    )
    embed.add_field(
        name="position",
        value="Screen position\n`center`, `top`, `bottom`, `left`, `right`, `topleft`, `topright`, `bottomleft`, `bottomright`\nDefault: `center`",
        inline=True
    )
    embed.add_field(
        name="scale",
        value="Size multiplier\n`0.1` to `5.0`\nDefault: `1.0`",
        inline=True
    )
    embed.add_field(
        name="key",
        value="Key to destroy GUI\n`none`, `x`, `delete`, `backspace`, `escape`, `p`, `m`, `k`, `f1`-`f4`\nDefault: `none`",
        inline=True
    )
    embed.add_field(
        name="name",
        value="GUI name (use `_` for spaces)\nDefault: `ConvertedGui`",
        inline=True
    )
    await ctx.send(embed=embed)


@bot.command(name='ping')
async def ping_cmd(ctx):
    """Check bot latency"""
    latency = round(bot.latency * 1000)
    color = 0x00ff00 if latency < 100 else 0xffff00 if latency < 200 else 0xff0000
    embed = discord.Embed(
        title="🏓 Pong!",
        description=f"Latency: **{latency}ms**",
        color=color
    )
    await ctx.send(embed=embed)


@bot.command(name='example')
async def example_cmd(ctx):
    """Show usage examples"""
    embed = discord.Embed(
        title="📚 Usage Examples",
        color=0x5865F2
    )
    embed.add_field(
        name="Basic Conversion",
        value="`!convert`\nConverts with default settings",
        inline=False
    )
    embed.add_field(
        name="Draggable GUI",
        value="`!convert true`\nMakes the GUI draggable",
        inline=False
    )
    embed.add_field(
        name="Custom Position",
        value="`!convert false topleft`\nPositions GUI at top-left",
        inline=False
    )
    embed.add_field(
        name="Scaled Up",
        value="`!convert true center 1.5`\nDraggable, centered, 1.5x size",
        inline=False
    )
    embed.add_field(
        name="With Close Key",
        value="`!convert true center 1.0 escape`\nPress Escape to close GUI",
        inline=False
    )
    embed.add_field(
        name="Full Example",
        value="`!convert true center 1.2 x My_Cool_GUI`\nAll options configured",
        inline=False
    )
    await ctx.send(embed=embed)


@bot.event
async def on_command_error(ctx, error):
    """Handle command errors"""
    if isinstance(error, commands.CommandNotFound):
        return
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Missing argument: {error.param.name}\nUse `!chelp` for help.")
    elif isinstance(error, commands.BadArgument):
        await ctx.send(f"❌ Invalid argument provided.\nUse `!cconfig` to see valid options.")
    else:
        await ctx.send(f"❌ An error occurred: {str(error)}")


async def main():
    """Main entry point"""
    await start_web_server()
    token = os.getenv('DISCORD_BOT_TOKEN')
    if token:
        await bot.start(token)
    else:
        print("❌ No DISCORD_BOT_TOKEN found in environment variables!")


if __name__ == "__main__":
    token = os.getenv('DISCORD_BOT_TOKEN')
    if token:
        asyncio.run(main())
    else:
        print("❌ No DISCORD_BOT_TOKEN environment variable set!")
