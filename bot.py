import discord
from discord.ext import commands
import xml.etree.ElementTree as ET
import io
import os
from aiohttp import web
import asyncio

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

async def handle(request):
    return web.Response(text="Bot is running!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle)
    app.router.add_get('/health', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get('PORT', 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f'Web server running on port {port}')

class RobloxConverter:
    def __init__(self):
        self.lua_code = []
        self.config = {
            'draggable': False,
            'position': 'center',
            'scale': 1.0,
            'destroykey': 'none',
            'gui_name': 'ConvertedGui',
            'transparency': None
        }
        self.enum_map = {
            'BorderMode': {0: 'Enum.BorderMode.Outline', 1: 'Enum.BorderMode.Middle', 2: 'Enum.BorderMode.Inset'},
            'ApplyStrokeMode': {0: 'Enum.ApplyStrokeMode.Contextual', 1: 'Enum.ApplyStrokeMode.Border'},
            'LineJoinMode': {0: 'Enum.LineJoinMode.Round', 1: 'Enum.LineJoinMode.Bevel', 2: 'Enum.LineJoinMode.Miter'},
            'FillDirection': {0: 'Enum.FillDirection.Horizontal', 1: 'Enum.FillDirection.Vertical'},
            'HorizontalAlignment': {0: 'Enum.HorizontalAlignment.Center', 1: 'Enum.HorizontalAlignment.Left', 2: 'Enum.HorizontalAlignment.Right'},
            'VerticalAlignment': {0: 'Enum.VerticalAlignment.Center', 1: 'Enum.VerticalAlignment.Top', 2: 'Enum.VerticalAlignment.Bottom'},
            'SizeConstraint': {0: 'Enum.SizeConstraint.RelativeXY', 1: 'Enum.SizeConstraint.RelativeXX', 2: 'Enum.SizeConstraint.RelativeYY'},
            'AutomaticSize': {0: 'Enum.AutomaticSize.None', 1: 'Enum.AutomaticSize.X', 2: 'Enum.AutomaticSize.Y', 3: 'Enum.AutomaticSize.XY'},
            'TextXAlignment': {0: 'Enum.TextXAlignment.Center', 1: 'Enum.TextXAlignment.Left', 2: 'Enum.TextXAlignment.Right'},
            'TextYAlignment': {0: 'Enum.TextYAlignment.Center', 1: 'Enum.TextYAlignment.Top', 2: 'Enum.TextYAlignment.Bottom'},
            'ScaleType': {0: 'Enum.ScaleType.Stretch', 1: 'Enum.ScaleType.Slice', 2: 'Enum.ScaleType.Tile', 3: 'Enum.ScaleType.Fit', 4: 'Enum.ScaleType.Crop'},
            'ResamplerMode': {0: 'Enum.ResamplerMode.Default', 1: 'Enum.ResamplerMode.Pixelated'},
            'ScrollingDirection': {0: 'Enum.ScrollingDirection.X', 1: 'Enum.ScrollingDirection.Y', 2: 'Enum.ScrollingDirection.XY'},
            'SortOrder': {0: 'Enum.SortOrder.Name', 1: 'Enum.SortOrder.Custom', 2: 'Enum.SortOrder.LayoutOrder'},
            'StartCorner': {0: 'Enum.StartCorner.TopLeft', 1: 'Enum.StartCorner.TopRight', 2: 'Enum.StartCorner.BottomLeft', 3: 'Enum.StartCorner.BottomRight'},
        }
        self.global_min_x = 0
        self.global_min_y = 0
    
    def set_config(self, **kwargs):
        self.config.update(kwargs)
    
    def get_udim2_from_element(self, item, prop_name):
        properties = item.find('Properties')
        if properties is None:
            return None
        for prop in properties:
            if prop.get('name') == prop_name and prop.tag == 'UDim2':
                xs = prop.find('XS')
                xo = prop.find('XO')
                ys = prop.find('YS')
                yo = prop.find('YO')
                return {
                    'xs': float(xs.text) if xs is not None and xs.text else 0,
                    'xo': float(xo.text) if xo is not None and xo.text else 0,
                    'ys': float(ys.text) if ys is not None and ys.text else 0,
                    'yo': float(yo.text) if yo is not None and yo.text else 0
                }
        return None
    
    def calculate_global_bounds(self, root):
        positions = []
        sizes = []
        
        for item in root.findall('.//Item'):
            pos = self.get_udim2_from_element(item, 'Position')
            size = self.get_udim2_from_element(item, 'Size')
            if pos:
                positions.append(pos)
            if size:
                sizes.append(size)
        
        if not positions:
            return 0, 0, 400, 300
        
        all_x = [p['xo'] for p in positions]
        all_y = [p['yo'] for p in positions]
        
        min_x = min(all_x)
        min_y = min(all_y)
        
        max_x = min_x
        max_y = min_y
        for i, pos in enumerate(positions):
            size = sizes[i] if i < len(sizes) else {'xo': 100, 'yo': 100}
            right = pos['xo'] + size['xo']
            bottom = pos['yo'] + size['yo']
            if right > max_x:
                max_x = right
            if bottom > max_y:
                max_y = bottom
        
        width = max_x - min_x
        height = max_y - min_y
        
        return min_x, min_y, max(width, 10), max(height, 10)
    
    def parse_property(self, prop_elem):
        prop_name = prop_elem.get('name')
        tag = prop_elem.tag
        
        if tag == 'string':
            text = prop_elem.text or ""
            text = text.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\r', '')
            return prop_name, f'"{text}"'
        elif tag == 'bool':
            val = prop_elem.text or "false"
            return prop_name, val.lower()
        elif tag == 'int':
            return prop_name, prop_elem.text or "0"
        elif tag == 'float':
            return prop_name, prop_elem.text or "0"
        elif tag == 'double':
            return prop_name, prop_elem.text or "0"
        elif tag == 'Color3':
            r = prop_elem.find('R')
            g = prop_elem.find('G')
            b = prop_elem.find('B')
            rv = r.text if r is not None and r.text else "0"
            gv = g.text if g is not None and g.text else "0"
            bv = b.text if b is not None and b.text else "0"
            return prop_name, f"Color3.new({rv}, {gv}, {bv})"
        elif tag == 'Color3uint8':
            if prop_elem.text:
                val = int(prop_elem.text)
                r = (val >> 16) & 0xFF
                g = (val >> 8) & 0xFF
                b = val & 0xFF
                return prop_name, f"Color3.fromRGB({r}, {g}, {b})"
            return prop_name, "Color3.new(1, 1, 1)"
        elif tag == 'UDim2':
            return prop_name, None
        elif tag == 'UDim':
            s = prop_elem.find('S')
            o = prop_elem.find('O')
            sv = s.text if s is not None and s.text else "0"
            ov = o.text if o is not None and o.text else "0"
            return prop_name, f"UDim.new({sv}, {ov})"
        elif tag == 'Vector2':
            x = prop_elem.find('X')
            y = prop_elem.find('Y')
            xv = x.text if x is not None and x.text else "0"
            yv = y.text if y is not None and y.text else "0"
            return prop_name, f"Vector2.new({xv}, {yv})"
        elif tag == 'Vector3':
            x = prop_elem.find('X')
            y = prop_elem.find('Y')
            z = prop_elem.find('Z')
            xv = x.text if x is not None and x.text else "0"
            yv = y.text if y is not None and y.text else "0"
            zv = z.text if z is not None and z.text else "0"
            return prop_name, f"Vector3.new({xv}, {yv}, {zv})"
        elif tag == 'token':
            token_val = int(prop_elem.text or "0")
            if prop_name in self.enum_map and token_val in self.enum_map[prop_name]:
                return prop_name, self.enum_map[prop_name][token_val]
            return prop_name, str(token_val)
        elif tag == 'Font':
            family = prop_elem.find('Family')
            weight = prop_elem.find('Weight')
            style = prop_elem.find('Style')
            font_url = "rbxasset://fonts/families/SourceSansPro.json"
            weight_val = "Regular"
            style_val = "Normal"
            if family is not None:
                url_elem = family.find('url')
                if url_elem is not None and url_elem.text:
                    font_url = url_elem.text
            if weight is not None and weight.text:
                weight_val = weight.text
            if style is not None and style.text:
                style_val = style.text
            weight_map = {'100': 'Thin', '200': 'ExtraLight', '300': 'Light', '400': 'Regular', '500': 'Medium', '600': 'SemiBold', '700': 'Bold', '800': 'ExtraBold', '900': 'Heavy'}
            if weight_val in weight_map:
                weight_val = weight_map[weight_val]
            return prop_name, f'Font.new("{font_url}", Enum.FontWeight.{weight_val}, Enum.FontStyle.{style_val})'
        elif tag == 'Rect':
            min_elem = prop_elem.find('min')
            max_elem = prop_elem.find('max')
            if min_elem is not None and max_elem is not None:
                mnx = min_elem.find('X')
                mny = min_elem.find('Y')
                mxx = max_elem.find('X')
                mxy = max_elem.find('Y')
                return prop_name, f"Rect.new({mnx.text if mnx is not None else 0}, {mny.text if mny is not None else 0}, {mxx.text if mxx is not None else 0}, {mxy.text if mxy is not None else 0})"
            return prop_name, None
        elif tag == 'NumberSequence':
            return prop_name, "NumberSequence.new(1)"
        elif tag == 'ColorSequence':
            return prop_name, "ColorSequence.new(Color3.new(1, 1, 1))"
        elif tag == 'NumberRange':
            if prop_elem.text:
                parts = prop_elem.text.split()
                if len(parts) >= 2:
                    return prop_name, f"NumberRange.new({parts[0]}, {parts[1]})"
            return prop_name, "NumberRange.new(0, 1)"
        elif tag == 'Ref':
            return prop_name, None
        elif tag == 'Content':
            url_elem = prop_elem.find('url')
            if url_elem is not None and url_elem.text:
                return prop_name, f'"{url_elem.text}"'
            elif prop_elem.text:
                text = prop_elem.text.replace('\\', '\\\\').replace('"', '\\"')
                return prop_name, f'"{text}"'
            return prop_name, '""'
        return prop_name, None
    
    def convert_item(self, item, var_name, parent_var, apply_offset):
        class_name = item.get('class')
        if not class_name:
            return
        
        self.lua_code.append(f'local {var_name} = Instance.new("{class_name}")')
        
        properties = item.find('Properties')
        if properties is not None:
            pos_data = None
            size_data = None
            
            for prop_elem in properties:
                pname = prop_elem.get('name')
                if pname == 'Position' and prop_elem.tag == 'UDim2':
                    pos_data = self.get_udim2_from_element(item, 'Position')
                elif pname == 'Size' and prop_elem.tag == 'UDim2':
                    size_data = self.get_udim2_from_element(item, 'Size')
            
            if size_data:
                new_xo = int(size_data['xo'] * self.config['scale'])
                new_yo = int(size_data['yo'] * self.config['scale'])
                self.lua_code.append(f'{var_name}.Size = UDim2.new({size_data["xs"]}, {new_xo}, {size_data["ys"]}, {new_yo})')
            
            if pos_data:
                if apply_offset:
                    new_xo = int((pos_data['xo'] - self.global_min_x) * self.config['scale'])
                    new_yo = int((pos_data['yo'] - self.global_min_y) * self.config['scale'])
                else:
                    new_xo = int(pos_data['xo'] * self.config['scale'])
                    new_yo = int(pos_data['yo'] * self.config['scale'])
                self.lua_code.append(f'{var_name}.Position = UDim2.new({pos_data["xs"]}, {new_xo}, {pos_data["ys"]}, {new_yo})')
            
            for prop_elem in properties:
                pname = prop_elem.get('name')
                if pname in ['Parent', 'Archivable', 'RobloxLocked', 'Position', 'Size']:
                    continue
                try:
                    result = self.parse_property(prop_elem)
                    if result and result[1] is not None:
                        self.lua_code.append(f'{var_name}.{result[0]} = {result[1]}')
                except Exception:
                    pass
        
        if self.config['transparency'] is not None:
            if class_name in ['Frame', 'TextLabel', 'TextButton', 'ImageLabel', 'ImageButton']:
                self.lua_code.append(f'{var_name}.BackgroundTransparency = {self.config["transparency"]}')
        
        self.lua_code.append(f'{var_name}.Parent = {parent_var}')
        self.lua_code.append('')
        
        child_counter = 1
        for child_item in item.findall('Item'):
            child_var = f"{var_name}_{child_counter}"
            self.convert_item(child_item, child_var, var_name, apply_offset=False)
            child_counter += 1
    
    def add_destroy_key(self):
        key_map = {
            'x': 'Enum.KeyCode.X',
            'delete': 'Enum.KeyCode.Delete', 
            'backspace': 'Enum.KeyCode.Backspace',
            'escape': 'Enum.KeyCode.Escape',
            'p': 'Enum.KeyCode.P',
            'm': 'Enum.KeyCode.M',
            'k': 'Enum.KeyCode.K'
        }
        key = self.config['destroykey'].lower()
        if key in key_map:
            self.lua_code.append(f"game:GetService('UserInputService').InputBegan:Connect(function(input, gp)")
            self.lua_code.append(f"\tif not gp and input.KeyCode == {key_map[key]} then")
            self.lua_code.append(f"\t\tscreenGui:Destroy()")
            self.lua_code.append(f"\tend")
            self.lua_code.append(f"end)")
            self.lua_code.append("")
    
    def add_draggable(self):
        self.lua_code.append("local UIS = game:GetService('UserInputService')")
        self.lua_code.append("local dragging, dragInput, dragStart, startPos")
        self.lua_code.append("local function updateDrag(input)")
        self.lua_code.append("\tlocal delta = input.Position - dragStart")
        self.lua_code.append("\tmainContainer.Position = UDim2.new(startPos.X.Scale, startPos.X.Offset + delta.X, startPos.Y.Scale, startPos.Y.Offset + delta.Y)")
        self.lua_code.append("end")
        self.lua_code.append("mainContainer.InputBegan:Connect(function(input)")
        self.lua_code.append("\tif input.UserInputType == Enum.UserInputType.MouseButton1 or input.UserInputType == Enum.UserInputType.Touch then")
        self.lua_code.append("\t\tdragging = true")
        self.lua_code.append("\t\tdragStart = input.Position")
        self.lua_code.append("\t\tstartPos = mainContainer.Position")
        self.lua_code.append("\t\tinput.Changed:Connect(function()")
        self.lua_code.append("\t\t\tif input.UserInputState == Enum.UserInputState.End then")
        self.lua_code.append("\t\t\t\tdragging = false")
        self.lua_code.append("\t\t\tend")
        self.lua_code.append("\t\tend)")
        self.lua_code.append("\tend")
        self.lua_code.append("end)")
        self.lua_code.append("mainContainer.InputChanged:Connect(function(input)")
        self.lua_code.append("\tif input.UserInputType == Enum.UserInputType.MouseMovement or input.UserInputType == Enum.UserInputType.Touch then")
        self.lua_code.append("\t\tdragInput = input")
        self.lua_code.append("\tend")
        self.lua_code.append("end)")
        self.lua_code.append("UIS.InputChanged:Connect(function(input)")
        self.lua_code.append("\tif input == dragInput and dragging then")
        self.lua_code.append("\t\tupdateDrag(input)")
        self.lua_code.append("\tend")
        self.lua_code.append("end)")
        self.lua_code.append("")
    
    def convert_rbxmx(self, xml_content):
        try:
            root = ET.fromstring(xml_content)
        except ET.ParseError as e:
            return f"-- XML Parse Error: {str(e)}"
        
        try:
            min_x, min_y, total_width, total_height = self.calculate_global_bounds(root)
            self.global_min_x = min_x
            self.global_min_y = min_y
            
            container_w = int(total_width * self.config['scale'])
            container_h = int(total_height * self.config['scale'])
            
            self.lua_code = []
            self.lua_code.append("local Players = game:GetService('Players')")
            self.lua_code.append("local player = Players.LocalPlayer")
            self.lua_code.append("local playerGui = player:WaitForChild('PlayerGui')")
            self.lua_code.append("")
            self.lua_code.append("local screenGui = Instance.new('ScreenGui')")
            self.lua_code.append(f"screenGui.Name = '{self.config['gui_name']}'")
            self.lua_code.append("screenGui.ResetOnSpawn = false")
            self.lua_code.append("screenGui.ZIndexBehavior = Enum.ZIndexBehavior.Sibling")
            self.lua_code.append("screenGui.Parent = playerGui")
            self.lua_code.append("")
            
            self.lua_code.append("local mainContainer = Instance.new('Frame')")
            self.lua_code.append("mainContainer.Name = 'MainContainer'")
            self.lua_code.append(f"mainContainer.Size = UDim2.new(0, {container_w}, 0, {container_h})")
            self.lua_code.append("mainContainer.BackgroundTransparency = 1")
            self.lua_code.append("mainContainer.BorderSizePixel = 0")
            
            pos = self.config['position']
            if pos == 'center':
                self.lua_code.append("mainContainer.Position = UDim2.new(0.5, 0, 0.5, 0)")
                self.lua_code.append("mainContainer.AnchorPoint = Vector2.new(0.5, 0.5)")
            elif pos == 'top':
                self.lua_code.append("mainContainer.Position = UDim2.new(0.5, 0, 0, 10)")
                self.lua_code.append("mainContainer.AnchorPoint = Vector2.new(0.5, 0)")
            elif pos == 'bottom':
                self.lua_code.append("mainContainer.Position = UDim2.new(0.5, 0, 1, -10)")
                self.lua_code.append("mainContainer.AnchorPoint = Vector2.new(0.5, 1)")
            elif pos == 'left':
                self.lua_code.append("mainContainer.Position = UDim2.new(0, 10, 0.5, 0)")
                self.lua_code.append("mainContainer.AnchorPoint = Vector2.new(0, 0.5)")
            elif pos == 'right':
                self.lua_code.append("mainContainer.Position = UDim2.new(1, -10, 0.5, 0)")
                self.lua_code.append("mainContainer.AnchorPoint = Vector2.new(1, 0.5)")
            elif pos == 'topleft':
                self.lua_code.append("mainContainer.Position = UDim2.new(0, 10, 0, 10)")
                self.lua_code.append("mainContainer.AnchorPoint = Vector2.new(0, 0)")
            elif pos == 'topright':
                self.lua_code.append("mainContainer.Position = UDim2.new(1, -10, 0, 10)")
                self.lua_code.append("mainContainer.AnchorPoint = Vector2.new(1, 0)")
            elif pos == 'bottomleft':
                self.lua_code.append("mainContainer.Position = UDim2.new(0, 10, 1, -10)")
                self.lua_code.append("mainContainer.AnchorPoint = Vector2.new(0, 1)")
            elif pos == 'bottomright':
                self.lua_code.append("mainContainer.Position = UDim2.new(1, -10, 1, -10)")
                self.lua_code.append("mainContainer.AnchorPoint = Vector2.new(1, 1)")
            elif pos == 'original':
                self.lua_code.append(f"mainContainer.Position = UDim2.new(0, 0, 0, 0)")
            
            self.lua_code.append("mainContainer.Parent = screenGui")
            self.lua_code.append("")
            
            item_counter = 1
            for item in root.findall('Item'):
                var_name = f"element{item_counter}"
                self.convert_item(item, var_name, "mainContainer", apply_offset=True)
                item_counter += 1
            
            if item_counter == 1:
                return "-- Error: No GUI elements found in file"
            
            if self.config['draggable']:
                self.add_draggable()
            
            if self.config['destroykey'] != 'none':
                self.add_destroy_key()
            
            return '\n'.join(self.lua_code)
            
        except Exception as e:
            return f"-- Error: {str(e)}"

converter = RobloxConverter()

@bot.event
async def on_ready():
    print(f'{bot.user} connected to Discord!')

@bot.command(name='convert')
async def convert_file(ctx, draggable: str = "false", position: str = "center", scale: float = 1.0, destroykey: str = "none", gui_name: str = "ConvertedGui", transparency: float = -1):
    if not ctx.message.attachments:
        await ctx.send("Please attach an RBXMX file!")
        return
    
    attachment = ctx.message.attachments[0]
    if not attachment.filename.lower().endswith('.rbxmx'):
        await ctx.send("Please use .rbxmx format!")
        return
    
    if attachment.size > 5000000:
        await ctx.send("File too large! Max 5MB.")
        return
    
    try:
        file_content = await attachment.read()
        xml_string = file_content.decode('utf-8')
        
        drag_bool = draggable.lower() == "true"
        
        valid_positions = ['center', 'top', 'bottom', 'left', 'right', 'topleft', 'topright', 'bottomleft', 'bottomright', 'original']
        pos_value = position.lower() if position.lower() in valid_positions else 'center'
        
        scale_value = scale if 0.1 <= scale <= 5.0 else 1.0
        
        valid_keys = ['none', 'x', 'delete', 'backspace', 'escape', 'p', 'm', 'k']
        key_value = destroykey.lower() if destroykey.lower() in valid_keys else 'none'
        
        name_value = gui_name.replace('_', ' ')
        
        trans_value = transparency if 0.0 <= transparency <= 1.0 else None
        
        status_msg = f"Converting: drag={drag_bool}, pos={pos_value}, scale={scale_value}x, key={key_value}, name={name_value}"
        if trans_value is not None:
            status_msg += f", trans={trans_value}"
        await ctx.send(status_msg)
        
        converter.set_config(
            draggable=drag_bool,
            position=pos_value,
            scale=scale_value,
            destroykey=key_value,
            gui_name=name_value,
            transparency=trans_value
        )
        
        lua_code = converter.convert_rbxmx(xml_string)
        
        output_filename = attachment.filename.replace('.rbxmx', '').replace('.RBXMX', '') + '_converted.lua'
        lua_file = discord.File(io.BytesIO(lua_code.encode('utf-8')), filename=output_filename)
        
        await ctx.send("Done!", file=lua_file)
        
    except Exception as e:
        await ctx.send(f"Error: {str(e)}")

@bot.command(name='chelp')
async def chelp(ctx):
    embed = discord.Embed(title="Bot Commands", color=discord.Color.green())
    embed.add_field(name="!convert", value="Convert RBXMX file to Lua", inline=False)
    embed.add_field(name="!cconfig", value="Show configuration options", inline=False)
    embed.add_field(name="!chelp", value="Show this help", inline=False)
    embed.add_field(name="!ping", value="Check bot status", inline=False)
    embed.add_field(name="!example", value="Show usage examples", inline=False)
    await ctx.send(embed=embed)

@bot.command(name='cconfig')
async def cconfig(ctx):
    embed = discord.Embed(title="Configuration Options", color=discord.Color.blue())
    embed.add_field(name="Usage", value="`!convert [drag] [pos] [scale] [key] [name] [trans]`", inline=False)
    embed.add_field(name="drag", value="true / false", inline=True)
    embed.add_field(name="pos", value="center/top/bottom/left/right/topleft/topright/bottomleft/bottomright/original", inline=True)
    embed.add_field(name="scale", value="0.1 to 5.0", inline=True)
    embed.add_field(name="key", value="none/x/delete/backspace/escape/p/m/k", inline=True)
    embed.add_field(name="name", value="GUI name (use _ for spaces)", inline=True)
    embed.add_field(name="trans", value="0.0-1.0", inline=True)
await ctx.send(embed=embed)

async def main():
    await start_web_server()
    await bot.start(os.getenv('DISCORD_BOT_TOKEN'))

if __name__ == "__main__":
    TOKEN = os.getenv('DISCORD_BOT_TOKEN')
    if not TOKEN:
        print("Error: DISCORD_BOT_TOKEN not set!")
    else:
        asyncio.run(main())
