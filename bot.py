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
    return web.Response(text="✅ Roblox Converter Bot is running!")

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
        self.indent_level = 0
        self.lua_code = []
        self.config = {
            'draggable': False,
            'position': 'center',
            'scale': 1.0,
            'ignore_offscreen': True
        }
    
    def set_config(self, **kwargs):
        self.config.update(kwargs)
    
    def indent(self):
        return "\t" * self.indent_level
    
    def parse_property_value(self, prop):
        prop_name = prop.get('name')
        
        if prop.find('string') is not None:
            text = prop.find('string').text or ""
            text = text.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
            return f'"{text}"'
        
        elif prop.find('ProtectedString') is not None:
            text = prop.find('ProtectedString').text or ""
            text = text.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
            return f'"{text}"'
        
        elif prop.find('bool') is not None:
            return prop.find('bool').text or "false"
        
        elif prop.find('int') is not None:
            return prop.find('int').text or "0"
        elif prop.find('int64') is not None:
            return prop.find('int64').text or "0"
        elif prop.find('float') is not None:
            return prop.find('float').text or "0"
        elif prop.find('double') is not None:
            return prop.find('double').text or "0"
        
        elif prop.find('Color3') is not None:
            color = prop.find('Color3')
            r = color.find('R').text if color.find('R') is not None else "0"
            g = color.find('G').text if color.find('G') is not None else "0"
            b = color.find('B').text if color.find('B') is not None else "0"
            return f"Color3.new({r}, {g}, {b})"
        
        elif prop.find('Color3uint8') is not None:
            color = prop.find('Color3uint8')
            r = int(color.text) >> 16 if color.text else 0
            g = (int(color.text) >> 8) & 0xFF if color.text else 0
            b = int(color.text) & 0xFF if color.text else 0
            return f"Color3.fromRGB({r}, {g}, {b})"
        
        elif prop.find('Vector2') is not None:
            vec = prop.find('Vector2')
            x = vec.find('X').text if vec.find('X') is not None else "0"
            y = vec.find('Y').text if vec.find('Y') is not None else "0"
            return f"Vector2.new({x}, {y})"
        
        elif prop.find('Vector3') is not None:
            vec = prop.find('Vector3')
            x = vec.find('X').text if vec.find('X') is not None else "0"
            y = vec.find('Y').text if vec.find('Y') is not None else "0"
            z = vec.find('Z').text if vec.find('Z') is not None else "0"
            return f"Vector3.new({x}, {y}, {z})"
        
        elif prop.find('UDim') is not None:
            udim = prop.find('UDim')
            s = udim.find('S').text if udim.find('S') is not None else "0"
            o = udim.find('O').text if udim.find('O') is not None else "0"
            return f"UDim.new({s}, {o})"
        
        elif prop.find('UDim2') is not None:
            udim = prop.find('UDim2')
            xs = udim.find('XS').text if udim.find('XS') is not None else "0"
            xo = udim.find('XO').text if udim.find('XO') is not None else "0"
            ys = udim.find('YS').text if udim.find('YS') is not None else "0"
            yo = udim.find('YO').text if udim.find('YO') is not None else "0"
            return f"UDim2.new({xs}, {xo}, {ys}, {yo})"
        
        elif prop.find('Rect') is not None:
            rect = prop.find('Rect')
            min_elem = rect.find('min')
            max_elem = rect.find('max')
            if min_elem is not None and max_elem is not None:
                min_x = min_elem.find('X').text if min_elem.find('X') is not None else "0"
                min_y = min_elem.find('Y').text if min_elem.find('Y') is not None else "0"
                max_x = max_elem.find('X').text if max_elem.find('X') is not None else "0"
                max_y = max_elem.find('Y').text if max_elem.find('Y') is not None else "0"
                return f"Rect.new({min_x}, {min_y}, {max_x}, {max_y})"
        
        elif prop.find('token') is not None:
            token_value = prop.find('token').text or "0"
            return token_value
        
        elif prop.find('BrickColor') is not None:
            brick_color = prop.find('BrickColor').text or "194"
            return f"BrickColor.new({brick_color})"
        
        elif prop.find('NumberSequence') is not None:
            return "NumberSequence.new(0)"
        
        elif prop.find('ColorSequence') is not None:
            return "ColorSequence.new(Color3.new(1,1,1))"
        
        elif prop.find('NumberRange') is not None:
            num_range = prop.find('NumberRange')
            min_val = num_range.text.split()[0] if num_range.text else "0"
            max_val = num_range.text.split()[1] if num_range.text and len(num_range.text.split()) > 1 else min_val
            return f"NumberRange.new({min_val}, {max_val})"
        
        elif prop.find('Ref') is not None:
            return "nil"
        
        elif prop.find('Font') is not None:
            font = prop.find('Font')
            family = font.find('Family')
            weight = font.find('Weight')
            style = font.find('Style')
            
            if family is not None and family.find('url') is not None:
                font_url = family.find('url').text or ""
                weight_val = weight.text if weight is not None else "Regular"
                style_val = style.text if style is not None else "Normal"
                
                if "rbxasset://fonts/families/" in font_url:
                    font_name = font_url.split("/")[-1].replace(".json", "")
                    return f'Font.new("rbxasset://fonts/families/{font_name}.json", Enum.FontWeight.{weight_val}, Enum.FontStyle.{style_val})'
            
            return 'Font.new("rbxasset://fonts/families/SourceSansPro.json")'
        
        return None
    
    def get_enum_from_token(self, class_name, prop_name, token_value):
        enum_map = {
            'BorderMode': {0: 'Enum.BorderMode.Outline', 1: 'Enum.BorderMode.Middle', 2: 'Enum.BorderMode.Inset'},
            'ApplyStrokeMode': {0: 'Enum.ApplyStrokeMode.Contextual', 1: 'Enum.ApplyStrokeMode.Border'},
            'LineJoinMode': {0: 'Enum.LineJoinMode.Round', 1: 'Enum.LineJoinMode.Bevel', 2: 'Enum.LineJoinMode.Miter'},
            'FillDirection': {0: 'Enum.FillDirection.Horizontal', 1: 'Enum.FillDirection.Vertical'},
            'HorizontalAlignment': {0: 'Enum.HorizontalAlignment.Center', 1: 'Enum.HorizontalAlignment.Left', 2: 'Enum.HorizontalAlignment.Right'},
            'VerticalAlignment': {0: 'Enum.VerticalAlignment.Center', 1: 'Enum.VerticalAlignment.Top', 2: 'Enum.VerticalAlignment.Bottom'},
            'SizeConstraint': {0: 'Enum.SizeConstraint.RelativeXY', 1: 'Enum.SizeConstraint.RelativeXX', 2: 'Enum.SizeConstraint.RelativeYY'},
            'AutomaticSize': {0: 'Enum.AutomaticSize.None', 1: 'Enum.AutomaticSize.X', 2: 'Enum.AutomaticSize.Y', 3: 'Enum.AutomaticSize.XY'},
            'EasingDirection': {0: 'Enum.EasingDirection.In', 1: 'Enum.EasingDirection.Out', 2: 'Enum.EasingDirection.InOut'},
            'EasingStyle': {0: 'Enum.EasingStyle.Linear', 1: 'Enum.EasingStyle.Sine', 2: 'Enum.EasingStyle.Back', 3: 'Enum.EasingStyle.Quad', 4: 'Enum.EasingStyle.Quart', 5: 'Enum.EasingStyle.Quint', 6: 'Enum.EasingStyle.Bounce', 7: 'Enum.EasingStyle.Elastic', 8: 'Enum.EasingStyle.Exponential', 9: 'Enum.EasingStyle.Circular', 10: 'Enum.EasingStyle.Cubic'},
            'TextXAlignment': {0: 'Enum.TextXAlignment.Center', 1: 'Enum.TextXAlignment.Left', 2: 'Enum.TextXAlignment.Right'},
            'TextYAlignment': {0: 'Enum.TextYAlignment.Center', 1: 'Enum.TextYAlignment.Top', 2: 'Enum.TextYAlignment.Bottom'},
        }
        
        try:
            token_int = int(token_value)
            if prop_name in enum_map and token_int in enum_map[prop_name]:
                return enum_map[prop_name][token_int]
        except:
            pass
        
        return token_value
    
    def convert_instance(self, item, var_name, parent_var="screenGui", is_root=False):
        class_name = item.get('class')
        
        self.lua_code.append(f'{self.indent()}local {var_name} = Instance.new("{class_name}")')
        
        properties = item.find('Properties')
        original_size = None
        
        if properties is not None:
            for prop in properties:
                prop_name = prop.get('name')
                
                skip_props = ['Parent', 'Archivable', 'RobloxLocked']
                if prop_name in skip_props:
                    continue
                
                if is_root and prop_name == 'Position' and self.config['position'] != 'original':
                    continue
                
                if is_root and prop_name == 'Size' and self.config['scale'] != 1.0:
                    size_elem = prop.find('UDim2')
                    if size_elem is not None:
                        xs = size_elem.find('XS').text if size_elem.find('XS') is not None else "0"
                        xo = size_elem.find('XO').text if size_elem.find('XO') is not None else "0"
                        ys = size_elem.find('YS').text if size_elem.find('YS') is not None else "0"
                        yo = size_elem.find('YO').text if size_elem.find('YO') is not None else "0"
                        original_size = (float(xs), float(xo), float(ys), float(yo))
                    continue
                
                try:
                    value = self.parse_property_value(prop)
                    
                    if value is None:
                        continue
                    
                    if prop.find('token') is not None:
                        value = self.get_enum_from_token(class_name, prop_name, value)
                    
                    self.lua_code.append(f'{self.indent()}{var_name}.{prop_name} = {value}')
                except Exception as e:
                    pass
        
        if is_root:
            if self.config['scale'] != 1.0 and original_size:
                xs, xo, ys, yo = original_size
                new_xo = int(xo * self.config['scale'])
                new_yo = int(yo * self.config['scale'])
                self.lua_code.append(f'{self.indent()}{var_name}.Size = UDim2.new({xs}, {new_xo}, {ys}, {new_yo})')
            
            if self.config['position'] == 'center':
                self.lua_code.append(f'{self.indent()}{var_name}.Position = UDim2.new(0.5, 0, 0.5, 0)')
                self.lua_code.append(f'{self.indent()}{var_name}.AnchorPoint = Vector2.new(0.5, 0.5)')
            elif self.config['position'] == 'top':
                self.lua_code.append(f'{self.indent()}{var_name}.Position = UDim2.new(0.5, 0, 0, 10)')
                self.lua_code.append(f'{self.indent()}{var_name}.AnchorPoint = Vector2.new(0.5, 0)')
            elif self.config['position'] == 'bottom':
                self.lua_code.append(f'{self.indent()}{var_name}.Position = UDim2.new(0.5, 0, 1, -10)')
                self.lua_code.append(f'{self.indent()}{var_name}.AnchorPoint = Vector2.new(0.5, 1)')
        
        self.lua_code.append(f'{self.indent()}{var_name}.Parent = {parent_var}')
        self.lua_code.append('')
        
        counter = 1
        for child in item.findall('Item'):
            child_var = f"{var_name}_{counter}"
            self.convert_instance(child, child_var, var_name, is_root=False)
            counter += 1
    
    def add_draggable_script(self, root_var):
        self.lua_code.append(f"local UserInputService = game:GetService('UserInputService')")
        self.lua_code.append(f"local dragging, dragInput, dragStart, startPos")
        self.lua_code.append(f"local function update(input)")
        self.lua_code.append(f"\tlocal delta = input.Position - dragStart")
        self.lua_code.append(f"\t{root_var}.Position = UDim2.new(startPos.X.Scale, startPos.X.Offset + delta.X, startPos.Y.Scale, startPos.Y.Offset + delta.Y)")
        self.lua_code.append(f"end")
        self.lua_code.append(f"{root_var}.InputBegan:Connect(function(input)")
        self.lua_code.append(f"\tif input.UserInputType == Enum.UserInputType.MouseButton1 or input.UserInputType == Enum.UserInputType.Touch then")
        self.lua_code.append(f"\t\tdragging = true")
        self.lua_code.append(f"\t\tdragStart = input.Position")
        self.lua_code.append(f"\t\tstartPos = {root_var}.Position")
        self.lua_code.append(f"\t\tinput.Changed:Connect(function()")
        self.lua_code.append(f"\t\t\tif input.UserInputState == Enum.UserInputState.End then dragging = false end")
        self.lua_code.append(f"\t\tend)")
        self.lua_code.append(f"\tend")
        self.lua_code.append(f"end)")
        self.lua_code.append(f"{root_var}.InputChanged:Connect(function(input)")
        self.lua_code.append(f"\tif input.UserInputType == Enum.UserInputType.MouseMovement or input.UserInputType == Enum.UserInputType.Touch then dragInput = input end")
        self.lua_code.append(f"end)")
        self.lua_code.append(f"UserInputService.InputChanged:Connect(function(input)")
        self.lua_code.append(f"\tif input == dragInput and dragging then update(input) end")
        self.lua_code.append(f"end)")
        self.lua_code.append("")
    
    def convert_rbxmx(self, xml_content):
        try:
            root = ET.fromstring(xml_content)
            
            self.lua_code = [
                "local Players = game:GetService('Players')",
                "local player = Players.LocalPlayer",
                "local playerGui = player:WaitForChild('PlayerGui')",
                "local screenGui = Instance.new('ScreenGui')",
                "screenGui.Name = 'ConvertedGui'",
                "screenGui.ResetOnSpawn = false",
                "screenGui.ZIndexBehavior = Enum.ZIndexBehavior.Sibling",
                "",
            ]
            
            counter = 1
            root_objects = []
            for item in root.findall('Item'):
                var_name = f"object{counter}"
                root_objects.append(var_name)
                self.convert_instance(item, var_name, "screenGui", is_root=True)
                counter += 1
            
            if counter == 1:
                return "-- Error: No items found in file"
            
            if self.config['draggable'] and root_objects:
                for root_obj in root_objects:
                    self.add_draggable_script(root_obj)
            
            self.lua_code.append("screenGui.Parent = playerGui")
            
            return '\n'.join(self.lua_code)
        
        except ET.ParseError as e:
            return f"-- XML Parse Error: {str(e)}"
        except Exception as e:
            return f"-- Error converting file: {str(e)}"

converter = RobloxConverter()

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    print(f'Bot is ready to convert RBXMX files!')

@bot.command(name='convert')
async def convert_file(ctx, draggable: str = "false", position: str = "center", scale: float = 1.0):
    """Convert RBXMX file with options: !convert [draggable=true/false] [position=center/top/bottom/original] [scale=1.0]"""
    
    if not ctx.message.attachments:
        await ctx.send("❌ Please attach an RBXMX file!")
        return
    
    attachment = ctx.message.attachments[0]
    
    if not (attachment.filename.endswith('.rbxmx') or attachment.filename.endswith('.rbxm')):
        await ctx.send("❌ Please attach a valid .rbxmx file!")
        return
    
    if attachment.size > 5_000_000:
        await ctx.send("❌ File too large! Max 5MB.")
        return
    
    try:
        file_content = await attachment.read()
        
        draggable_bool = draggable.lower() == "true"
        
        valid_positions = ['center', 'top', 'bottom', 'original']
        if position.lower() not in valid_positions:
            position = 'center'
        
        if scale <= 0 or scale > 5:
            scale = 1.0
        
        config_text = f"🔄 Converting with settings: Draggable={draggable_bool}, Position={position}, Scale={scale}x"
        await ctx.send(config_text)
        
        converter.set_config(draggable=draggable_bool, position=position.lower(), scale=scale)
        
        if attachment.filename.endswith('.rbxmx'):
            lua_code = converter.convert_rbxmx(file_content.decode('utf-8'))
        else:
            await ctx.send("⚠️ RBXM files not supported. Use RBXMX format!")
            return
        
        lua_file = discord.File(
            io.BytesIO(lua_code.encode('utf-8')),
            filename=f"{attachment.filename.replace('.rbxmx', '').replace('.rbxm', '')}_converted.lua"
        )
        await ctx.send("✅ Conversion complete!", file=lua_file)
    
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)}")
        print(f"Error: {e}")

@bot.command(name='help_convert')
async def help_convert(ctx):
    help_text = """
**Roblox Converter Bot - Executor Ready**

**Basic Usage:**
`!convert` - Convert with default settings (centered, not draggable)

**Advanced Usage:**
`!convert true center 1.5` - Make draggable, centered, 1.5x size
`!convert false top 1.0` - Not draggable, top position, normal size
`!convert true original 0.8` - Draggable, original position, 80% size

**Parameters:**
• **draggable**: true/false - Makes GUI draggable
• **position**: center/top/bottom/original - Where to place GUI
• **scale**: 0.1-5.0 - Size multiplier (1.0 = normal)

**Examples:**
`!convert true center 2.0` - Draggable, centered, 2x bigger
`!convert false bottom 1.0` - Static, bottom screen
`!convert true original 1.0` - Draggable, keeps original position

**Supported Elements:**
Frames, TextLabels, TextButtons, ImageLabels, UIStroke, UICorner, UIGradient, and more!
    """
    embed = discord.Embed(
        title="🤖 Roblox GUI Converter",
        description=help_text,
        color=discord.Color.blue()
    )
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
