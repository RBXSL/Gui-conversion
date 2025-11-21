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
        self.all_positions = []
        self.all_sizes = []
    
    def set_config(self, **kwargs):
        self.config.update(kwargs)
    
    def get_position_from_item(self, item):
        properties = item.find('Properties')
        if properties is not None:
            for prop in properties:
                if prop.get('name') == 'Position' and prop.tag == 'UDim2':
                    xo = float(prop.find('XO').text if prop.find('XO') is not None else "0")
                    yo = float(prop.find('YO').text if prop.find('YO') is not None else "0")
                    return (xo, yo)
        return (0, 0)
    
    def get_size_from_item(self, item):
        properties = item.find('Properties')
        if properties is not None:
            for prop in properties:
                if prop.get('name') == 'Size' and prop.tag == 'UDim2':
                    xo = float(prop.find('XO').text if prop.find('XO') is not None else "0")
                    yo = float(prop.find('YO').text if prop.find('YO') is not None else "0")
                    return (xo, yo)
        return (0, 0)
    
    def collect_bounds(self, root):
        self.all_positions = []
        self.all_sizes = []
        for item in root.findall('Item'):
            pos = self.get_position_from_item(item)
            size = self.get_size_from_item(item)
            self.all_positions.append(pos)
            self.all_sizes.append(size)
        
        if not self.all_positions:
            return (0, 0, 100, 100)
        
        min_x = min(p[0] for p in self.all_positions)
        min_y = min(p[1] for p in self.all_positions)
        max_x = max(p[0] + s[0] for p, s in zip(self.all_positions, self.all_sizes))
        max_y = max(p[1] + s[1] for p, s in zip(self.all_positions, self.all_sizes))
        
        return (min_x, min_y, max_x - min_x, max_y - min_y)
    
    def parse_property(self, prop_elem):
        prop_name = prop_elem.get('name')
        tag = prop_elem.tag
        
        if tag == 'string':
            text = prop_elem.text or ""
            text = text.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
            return prop_name, f'"{text}"'
        elif tag == 'bool':
            return prop_name, prop_elem.text or "false"
        elif tag == 'int':
            return prop_name, prop_elem.text or "0"
        elif tag == 'float':
            return prop_name, prop_elem.text or "0"
        elif tag == 'double':
            return prop_name, prop_elem.text or "0"
        elif tag == 'Color3':
            r = prop_elem.find('R').text if prop_elem.find('R') is not None else "0"
            g = prop_elem.find('G').text if prop_elem.find('G') is not None else "0"
            b = prop_elem.find('B').text if prop_elem.find('B') is not None else "0"
            return prop_name, f"Color3.new({r}, {g}, {b})"
        elif tag == 'Color3uint8':
            if prop_elem.text:
                val = int(prop_elem.text)
                r = (val >> 16) & 0xFF
                g = (val >> 8) & 0xFF
                b = val & 0xFF
                return prop_name, f"Color3.fromRGB({r}, {g}, {b})"
            return prop_name, "Color3.new(1, 1, 1)"
        elif tag == 'UDim2':
            xs = prop_elem.find('XS').text if prop_elem.find('XS') is not None else "0"
            xo = prop_elem.find('XO').text if prop_elem.find('XO') is not None else "0"
            ys = prop_elem.find('YS').text if prop_elem.find('YS') is not None else "0"
            yo = prop_elem.find('YO').text if prop_elem.find('YO') is not None else "0"
            return prop_name, f"UDim2.new({xs}, {xo}, {ys}, {yo})"
        elif tag == 'UDim':
            s = prop_elem.find('S').text if prop_elem.find('S') is not None else "0"
            o = prop_elem.find('O').text if prop_elem.find('O') is not None else "0"
            return prop_name, f"UDim.new({s}, {o})"
        elif tag == 'Vector2':
            x = prop_elem.find('X').text if prop_elem.find('X') is not None else "0"
            y = prop_elem.find('Y').text if prop_elem.find('Y') is not None else "0"
            return prop_name, f"Vector2.new({x}, {y})"
        elif tag == 'Vector3':
            x = prop_elem.find('X').text if prop_elem.find('X') is not None else "0"
            y = prop_elem.find('Y').text if prop_elem.find('Y') is not None else "0"
            z = prop_elem.find('Z').text if prop_elem.find('Z') is not None else "0"
            return prop_name, f"Vector3.new({x}, {y}, {z})"
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
                min_x = min_elem.find('X').text if min_elem.find('X') is not None else "0"
                min_y = min_elem.find('Y').text if min_elem.find('Y') is not None else "0"
                max_x = max_elem.find('X').text if max_elem.find('X') is not None else "0"
                max_y = max_elem.find('Y').text if max_elem.find('Y') is not None else "0"
                return prop_name, f"Rect.new({min_x}, {min_y}, {max_x}, {max_y})"
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
            if prop_elem.text:
                text = prop_elem.text.replace('\\', '\\\\').replace('"', '\\"')
                return prop_name, f'"{text}"'
            url_elem = prop_elem.find('url')
            if url_elem is not None and url_elem.text:
                return prop_name, f'"{url_elem.text}"'
            return prop_name, '""'
        return prop_name, None
    
    def convert_instance(self, item, var_name, parent_var, offset_x=0, offset_y=0):
        class_name = item.get('class')
        self.lua_code.append(f'local {var_name} = Instance.new("{class_name}")')
        properties = item.find('Properties')
        if properties is not None:
            for prop_elem in properties:
                prop_name = prop_elem.get('name')
                if prop_name in ['Parent', 'Archivable', 'RobloxLocked']:
                    continue
                if prop_name == 'Position' and prop_elem.tag == 'UDim2':
                    xs = prop_elem.find('XS').text if prop_elem.find('XS') is not None else "0"
                    xo = float(prop_elem.find('XO').text if prop_elem.find('XO') is not None else "0")
                    ys = prop_elem.find('YS').text if prop_elem.find('YS') is not None else "0"
                    yo = float(prop_elem.find('YO').text if prop_elem.find('YO') is not None else "0")
                    new_xo = int((xo - offset_x) * self.config['scale'])
                    new_yo = int((yo - offset_y) * self.config['scale'])
                    self.lua_code.append(f'{var_name}.Position = UDim2.new({xs}, {new_xo}, {ys}, {new_yo})')
                    continue
                if prop_name == 'Size' and prop_elem.tag == 'UDim2':
                    xs = prop_elem.find('XS').text if prop_elem.find('XS') is not None else "0"
                    xo = float(prop_elem.find('XO').text if prop_elem.find('XO') is not None else "0")
                    ys = prop_elem.find('YS').text if prop_elem.find('YS') is not None else "0"
                    yo = float(prop_elem.find('YO').text if prop_elem.find('YO') is not None else "0")
                    new_xo = int(xo * self.config['scale'])
                    new_yo = int(yo * self.config['scale'])
                    self.lua_code.append(f'{var_name}.Size = UDim2.new({xs}, {new_xo}, {ys}, {new_yo})')
                    continue
                try:
                    parsed = self.parse_property(prop_elem)
                    if parsed and parsed[1] is not None:
                        self.lua_code.append(f'{var_name}.{parsed[0]} = {parsed[1]}')
                except:
                    pass
        if self.config['transparency'] is not None and class_name in ['Frame', 'TextLabel', 'TextButton', 'ImageLabel', 'ImageButton']:
            self.lua_code.append(f'{var_name}.BackgroundTransparency = {self.config["transparency"]}')
        self.lua_code.append(f'{var_name}.Parent = {parent_var}')
        self.lua_code.append('')
        counter = 1
        for child in item.findall('Item'):
            child_var = f"{var_name}_{counter}"
            self.convert_instance(child, child_var, var_name, 0, 0)
            counter += 1
    
    def add_destroy_key(self):
        key_map = {'x': 'Enum.KeyCode.X', 'delete': 'Enum.KeyCode.Delete', 'backspace': 'Enum.KeyCode.Backspace', 'escape': 'Enum.KeyCode.Escape', 'p': 'Enum.KeyCode.P', 'm': 'Enum.KeyCode.M', 'k': 'Enum.KeyCode.K'}
        key = self.config['destroykey'].lower()
        if key in key_map:
            self.lua_code.append(f"game:GetService('UserInputService').InputBegan:Connect(function(input, gameProcessed)")
            self.lua_code.append(f"\tif not gameProcessed and input.KeyCode == {key_map[key]} then")
            self.lua_code.append(f"\t\tscreenGui:Destroy()")
            self.lua_code.append(f"\tend")
            self.lua_code.append(f"end)")
            self.lua_code.append("")
    
    def add_draggable(self, var_name):
        self.lua_code.append(f"local UIS = game:GetService('UserInputService')")
        self.lua_code.append(f"local dragging, dragInput, dragStart, startPos")
        self.lua_code.append(f"local function update(input)")
        self.lua_code.append(f"\tlocal delta = input.Position - dragStart")
        self.lua_code.append(f"\t{var_name}.Position = UDim2.new(startPos.X.Scale, startPos.X.Offset + delta.X, startPos.Y.Scale, startPos.Y.Offset + delta.Y)")
        self.lua_code.append(f"end")
        self.lua_code.append(f"{var_name}.InputBegan:Connect(function(input)")
        self.lua_code.append(f"\tif input.UserInputType == Enum.UserInputType.MouseButton1 or input.UserInputType == Enum.UserInputType.Touch then")
        self.lua_code.append(f"\t\tdragging = true")
        self.lua_code.append(f"\t\tdragStart = input.Position")
        self.lua_code.append(f"\t\tstartPos = {var_name}.Position")
        self.lua_code.append(f"\t\tinput.Changed:Connect(function()")
        self.lua_code.append(f"\t\t\tif input.UserInputState == Enum.UserInputState.End then dragging = false end")
        self.lua_code.append(f"\t\tend)")
        self.lua_code.append(f"\tend")
        self.lua_code.append(f"end)")
        self.lua_code.append(f"{var_name}.InputChanged:Connect(function(input)")
        self.lua_code.append(f"\tif input.UserInputType == Enum.UserInputType.MouseMovement or input.UserInputType == Enum.UserInputType.Touch then dragInput = input end")
        self.lua_code.append(f"end)")
        self.lua_code.append(f"UIS.InputChanged:Connect(function(input)")
        self.lua_code.append(f"\tif input == dragInput and dragging then update(input) end")
        self.lua_code.append(f"end)")
        self.lua_code.append("")
    
    def convert_rbxmx(self, xml_content):
        try:
            root = ET.fromstring(xml_content)
            bounds = self.collect_bounds(root)
            min_x, min_y, total_width, total_height = bounds
            self.lua_code = [
                "local Players = game:GetService('Players')",
                "local player = Players.LocalPlayer",
                "local playerGui = player:WaitForChild('PlayerGui')",
                "",
                "local screenGui = Instance.new('ScreenGui')",
                f"screenGui.Name = '{self.config['gui_name']}'",
                "screenGui.ResetOnSpawn = false",
                "screenGui.ZIndexBehavior = Enum.ZIndexBehavior.Sibling",
                "screenGui.Parent = playerGui",
                "",
            ]
            container_width = int(total_width * self.config['scale'])
            container_height = int(total_height * self.config['scale'])
            self.lua_code.append("local mainContainer = Instance.new('Frame')")
            self.lua_code.append("mainContainer.Name = 'MainContainer'")
            self.lua_code.append(f"mainContainer.Size = UDim2.new(0, {container_width}, 0, {container_height})")
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
                self.lua_code.append(f"mainContainer.Position = UDim2.new(0, {int(min_x)}, 0, {int(min_y)})")
            self.lua_code.append("mainContainer.Parent = screenGui")
            self.lua_code.append("")
            counter = 1
            for item in root.findall('Item'):
                var_name = f"object{counter}"
                self.convert_instance(item, var_name, "mainContainer", min_x, min_y)
                counter += 1
            if counter == 1:
                return "-- Error: No items found in file"
            if self.config['draggable']:
                self.add_draggable("mainContainer")
            if self.config['destroykey'] != 'none':
                self.add_destroy_key()
            return '\n'.join(self.lua_code)
        except ET.ParseError as e:
            return f"-- XML Parse Error: {str(e)}"
        except Exception as e:
            return f"-- Error: {str(e)}"

converter = RobloxConverter()

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')

@bot.command(name='convert')
async def convert_file(ctx, draggable: str = "false", position: str = "center", scale: float = 1.0, destroykey: str = "none", gui_name: str = "ConvertedGui", transparency: float = -1):
    if not ctx.message.attachments:
        await ctx.send("Please attach an RBXMX file!")
        return
    attachment = ctx.message.attachments[0]
    if not attachment.filename.endswith('.rbxmx'):
        await ctx.send("Please attach a .rbxmx file!")
        return
    if attachment.size > 5_000_000:
        await ctx.send("File too large! Max 5MB.")
        return
    try:
        file_content = await attachment.read()
        draggable_bool = draggable.lower() == "true"
        valid_positions = ['center', 'top', 'bottom', 'left', 'right', 'topleft', 'topright', 'bottomleft', 'bottomright', 'original']
        if position.lower() not in valid_positions:
            position = 'center'
        if scale <= 0 or scale > 5:
            scale = 1.0
        valid_keys = ['none', 'x', 'delete', 'backspace', 'escape', 'p', 'm', 'k']
        if destroykey.lower() not in valid_keys:
            destroykey = 'none'
        gui_name = gui_name.replace('_', ' ')
        trans_value = None if transparency < 0 or transparency > 1 else transparency
        config_msg = f"Draggable={draggable_bool} | Position={position} | Scale={scale}x | DestroyKey={destroykey} | Name={gui_name}"
        if trans_value is not None:
            config_msg += f" | Transparency={trans_value}"
        await ctx.send(config_msg)
        converter.set_config(draggable=draggable_bool, position=position.lower(), scale=scale, destroykey=destroykey.lower(), gui_name=gui_name, transparency=trans_value)
        lua_code = converter.convert_rbxmx(file_content.decode('utf-8'))
        lua_file = discord.File(io.BytesIO(lua_code.encode('utf-8')), filename=f"{attachment.filename.replace('.rbxmx', '')}_converted.lua")
        await ctx.send("Done!", file=lua_file)
    except Exception as e:
        await ctx.send(f"Error: {str(e)}")

@bot.command(name='chelp')
async def chelp(ctx):
    embed = discord.Embed(title="Bot Commands", color=discord.Color.green())
    embed.add_field(name="!convert", value="Convert RBXMX to Lua", inline=False)
    embed.add_field(name="!cconfig", value="Show config options", inline=False)
    embed.add_field(name="!chelp", value="Show this help", inline=False)
    embed.add_field(name="!ping", value="Check bot status", inline=False)
    embed.add_field(name="!example", value="Show examples", inline=False)
    await ctx.send(embed=embed)

@bot.command(name='cconfig')
async def cconfig(ctx):
    embed = discord.Embed(title="Configuration Options", color=discord.Color.blue())
    embed.add_field(name="Usage", value="`!convert [drag] [pos] [scale] [key] [name] [trans]`", inline=False)
    embed.add_field(name="draggable", value="true / false", inline=True)
    embed.add_field(name="position", value="center/top/bottom/left/right/topleft/topright/bottomleft/bottomright/original", inline=True)
    embed.add_field(name="scale", value="0.1 - 5.0", inline=True)
    embed.add_field(name="destroykey", value="none/x/delete/backspace/escape/p/m/k", inline=True)
    embed.add_field(name="gui_name", value="Any text (use _ for spaces)", inline=True)
    embed.add_field(name="transparency", value="0.0 - 1.0", inline=True)
    await ctx.send(embed=embed)

@bot.command(name='ping')
async def ping(ctx):
    await ctx.send(f"Pong! {round(bot.latency * 1000)}ms")

@bot.command(name='example')
async def example(ctx):
    embed = discord.Embed(title="Examples", color=discord.Color.purple())
    embed.add_field(name="Basic", value="`!convert`", inline=False)
    embed.add_field(name="Draggable centered", value="`!convert true center`", inline=False)
    embed.add_field(name="Top-left scaled", value="`!convert true topleft 1.5`", inline=False)
    embed.add_field(name="With close key", value="`!convert true center 1.0 x`", inline=False)
    embed.add_field(name="Full config", value="`!convert true center 1.2 escape My_GUI 0.3`", inline=False)
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
