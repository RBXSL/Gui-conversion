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
        self.min_x = 0
        self.min_y = 0
        self.width = 0
        self.height = 0
        self.zindex = 1
        self.enums = {
            'ApplyStrokeMode': {0: 'Enum.ApplyStrokeMode.Contextual', 1: 'Enum.ApplyStrokeMode.Border'},
            'LineJoinMode': {0: 'Enum.LineJoinMode.Round', 1: 'Enum.LineJoinMode.Bevel', 2: 'Enum.LineJoinMode.Miter'},
            'TextXAlignment': {0: 'Enum.TextXAlignment.Center', 1: 'Enum.TextXAlignment.Left', 2: 'Enum.TextXAlignment.Right'},
            'TextYAlignment': {0: 'Enum.TextYAlignment.Center', 1: 'Enum.TextYAlignment.Top', 2: 'Enum.TextYAlignment.Bottom'},
            'AutomaticSize': {0: 'Enum.AutomaticSize.None', 1: 'Enum.AutomaticSize.X', 2: 'Enum.AutomaticSize.Y', 3: 'Enum.AutomaticSize.XY'},
            'ScaleType': {0: 'Enum.ScaleType.Stretch', 1: 'Enum.ScaleType.Slice', 2: 'Enum.ScaleType.Tile', 3: 'Enum.ScaleType.Fit', 4: 'Enum.ScaleType.Crop'},
            'FillDirection': {0: 'Enum.FillDirection.Horizontal', 1: 'Enum.FillDirection.Vertical'},
            'HorizontalAlignment': {0: 'Enum.HorizontalAlignment.Center', 1: 'Enum.HorizontalAlignment.Left', 2: 'Enum.HorizontalAlignment.Right'},
            'VerticalAlignment': {0: 'Enum.VerticalAlignment.Center', 1: 'Enum.VerticalAlignment.Top', 2: 'Enum.VerticalAlignment.Bottom'},
            'SortOrder': {0: 'Enum.SortOrder.Name', 1: 'Enum.SortOrder.Custom', 2: 'Enum.SortOrder.LayoutOrder'},
            'ResamplerMode': {0: 'Enum.ResamplerMode.Default', 1: 'Enum.ResamplerMode.Pixelated'},
            'BorderMode': {0: 'Enum.BorderMode.Outline', 1: 'Enum.BorderMode.Middle', 2: 'Enum.BorderMode.Inset'},
        }

    def set_config(self, **kw):
        self.config = kw
        self.scale = kw.get('scale', 1.0)

    def w(self, line):
        self.lines.append(line)

    def get_udim2(self, props, name):
        for p in props:
            if p.get('name') == name and p.tag == 'UDim2':
                return {
                    'xs': float(p.findtext('XS') or 0),
                    'xo': float(p.findtext('XO') or 0),
                    'ys': float(p.findtext('YS') or 0),
                    'yo': float(p.findtext('YO') or 0)
                }
        return None

    def get_udim(self, props, name):
        for p in props:
            if p.get('name') == name and p.tag == 'UDim':
                return {
                    's': float(p.findtext('S') or 0),
                    'o': float(p.findtext('O') or 0)
                }
        return None

    def get_color3(self, props, name):
        for p in props:
            if p.get('name') == name and p.tag == 'Color3':
                return {
                    'r': float(p.findtext('R') or 0),
                    'g': float(p.findtext('G') or 0),
                    'b': float(p.findtext('B') or 0)
                }
        return None

    def get_str(self, props, name):
        for p in props:
            if p.get('name') == name and p.tag == 'string':
                return p.text or ''
        return None

    def get_float(self, props, name):
        for p in props:
            if p.get('name') == name and p.tag == 'float':
                return float(p.text or 0)
        return None

    def get_int(self, props, name):
        for p in props:
            if p.get('name') == name and p.tag == 'int':
                return int(p.text or 0)
        return None

    def get_bool(self, props, name):
        for p in props:
            if p.get('name') == name and p.tag == 'bool':
                return p.text == 'true'
        return None

    def get_token(self, props, name):
        for p in props:
            if p.get('name') == name and p.tag == 'token':
                return int(p.text or 0)
        return None

    def get_font(self, props, name):
        for p in props:
            if p.get('name') == name and p.tag == 'Font':
                fam = p.find('Family')
                url = 'rbxasset://fonts/families/SourceSansPro.json'
                if fam is not None:
                    u = fam.find('url')
                    if u is not None and u.text:
                        url = u.text
                wgt = p.findtext('Weight') or '400'
                sty = p.findtext('Style') or 'Normal'
                wmap = {'100':'Thin','200':'ExtraLight','300':'Light','400':'Regular','500':'Medium','600':'SemiBold','700':'Bold','800':'ExtraBold','900':'Heavy'}
                return {'url': url, 'weight': wmap.get(wgt, wgt), 'style': sty}
        return None

    def get_content(self, props, name):
        for p in props:
            if p.get('name') == name and p.tag == 'Content':
                u = p.find('url')
                if u is not None and u.text and u.text != 'undefined':
                    return u.text
        return None

    def calc_bounds(self, root):
        min_x = float('inf')
        min_y = float('inf')
        max_x = float('-inf')
        max_y = float('-inf')
        
        for item in root.findall('Item'):
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
            return 0, 0, 400, 300
        
        return min_x, min_y, max_x - min_x, max_y - min_y

    def enum_str(self, name, val):
        return self.enums.get(name, {}).get(val, str(val))

    def is_ui_component(self, cls):
        return cls in ['UIStroke', 'UICorner', 'UIGradient', 'UIListLayout', 'UIGridLayout', 'UIPadding', 'UIAspectRatioConstraint', 'UISizeConstraint', 'UIScale', 'UITextSizeConstraint']

    def write_element(self, item, var, parent, apply_offset):
        cls = item.get('class')
        if not cls:
            return
        
        props = item.find('Properties')
        self.w(f"local {var} = Instance.new('{cls}')")
        
        self.zindex += 1
        
        if props is not None:
            name = self.get_str(props, 'Name')
            if name:
                name = name.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '')
                self.w(f'{var}.Name = "{name}"')
            
            if not self.is_ui_component(cls):
                size = self.get_udim2(props, 'Size')
                if size:
                    xo = int(size['xo'] * self.scale)
                    yo = int(size['yo'] * self.scale)
                    self.w(f"{var}.Size = UDim2.new({size['xs']}, {xo}, {size['ys']}, {yo})")
                
                pos = self.get_udim2(props, 'Position')
                if pos:
                    if apply_offset:
                        xo = int((pos['xo'] - self.min_x) * self.scale)
                        yo = int((pos['yo'] - self.min_y) * self.scale)
                    else:
                        xo = int(pos['xo'] * self.scale)
                        yo = int(pos['yo'] * self.scale)
                    self.w(f"{var}.Position = UDim2.new({pos['xs']}, {xo}, {pos['ys']}, {yo})")
                
                self.w(f"{var}.ZIndex = {self.zindex}")
            
            bg_color = self.get_color3(props, 'BackgroundColor3')
            if bg_color:
                self.w(f"{var}.BackgroundColor3 = Color3.new({bg_color['r']}, {bg_color['g']}, {bg_color['b']})")
            
            bg_trans = self.get_float(props, 'BackgroundTransparency')
            if bg_trans is not None:
                self.w(f"{var}.BackgroundTransparency = {bg_trans}")
            
            border = self.get_int(props, 'BorderSizePixel')
            if border is not None:
                self.w(f"{var}.BorderSizePixel = {border}")
            
            visible = self.get_bool(props, 'Visible')
            if visible is not None:
                self.w(f"{var}.Visible = {str(visible).lower()}")
            
            text_color = self.get_color3(props, 'TextColor3')
            if text_color:
                self.w(f"{var}.TextColor3 = Color3.new({text_color['r']}, {text_color['g']}, {text_color['b']})")
            
            text_trans = self.get_float(props, 'TextTransparency')
            if text_trans is not None:
                self.w(f"{var}.TextTransparency = {text_trans}")
            
            text_size = self.get_int(props, 'TextSize')
            if text_size is not None:
                self.w(f"{var}.TextSize = {int(text_size * self.scale)}")
            
            text = self.get_str(props, 'Text')
            if text is not None:
                text = text.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
                self.w(f'{var}.Text = "{text}"')
            
            text_wrapped = self.get_bool(props, 'TextWrapped')
            if text_wrapped is not None:
                self.w(f"{var}.TextWrapped = {str(text_wrapped).lower()}")
            
            text_x = self.get_token(props, 'TextXAlignment')
            if text_x is not None:
                self.w(f"{var}.TextXAlignment = {self.enum_str('TextXAlignment', text_x)}")
            
            text_y = self.get_token(props, 'TextYAlignment')
            if text_y is not None:
                self.w(f"{var}.TextYAlignment = {self.enum_str('TextYAlignment', text_y)}")
            
            auto_size = self.get_token(props, 'AutomaticSize')
            if auto_size is not None:
                self.w(f"{var}.AutomaticSize = {self.enum_str('AutomaticSize', auto_size)}")
            
            font = self.get_font(props, 'FontFace')
            if font:
                self.w(f'{var}.FontFace = Font.new("{font["url"]}", Enum.FontWeight.{font["weight"]}, Enum.FontStyle.{font["style"]})')
            
            image = self.get_content(props, 'Image')
            if image:
                self.w(f'{var}.Image = "{image}"')
            
            image_trans = self.get_float(props, 'ImageTransparency')
            if image_trans is not None:
                self.w(f"{var}.ImageTransparency = {image_trans}")
            
            image_color = self.get_color3(props, 'ImageColor3')
            if image_color:
                self.w(f"{var}.ImageColor3 = Color3.new({image_color['r']}, {image_color['g']}, {image_color['b']})")
            
            scale_type = self.get_token(props, 'ScaleType')
            if scale_type is not None:
                self.w(f"{var}.ScaleType = {self.enum_str('ScaleType', scale_type)}")
            
            color = self.get_color3(props, 'Color')
            if color:
                self.w(f"{var}.Color = Color3.new({color['r']}, {color['g']}, {color['b']})")
            
            trans = self.get_float(props, 'Transparency')
            if trans is not None:
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
            
            corner = self.get_udim(props, 'CornerRadius')
            if corner:
                self.w(f"{var}.CornerRadius = UDim.new({corner['s']}, {int(corner['o'] * self.scale)})")
            
            rotation = self.get_float(props, 'Rotation')
            if rotation is not None:
                self.w(f"{var}.Rotation = {rotation}")
            
            anchor = self.get_udim2(props, 'AnchorPoint')
            if anchor:
                self.w(f"{var}.AnchorPoint = Vector2.new({anchor['xo']}, {anchor['yo']})")
            
            clip = self.get_bool(props, 'ClipsDescendants')
            if clip is not None:
                self.w(f"{var}.ClipsDescendants = {str(clip).lower()}")
        
        self.w(f"{var}.Parent = {parent}")
        self.w("")
        
        ci = 1
        for child in item.findall('Item'):
            self.write_element(child, f'{var}_{ci}', var, False)
            ci += 1

    def convert(self, xml_str):
        try:
            root = ET.fromstring(xml_str)
        except ET.ParseError as e:
            return f'-- XML Error: {e}'
        
        self.min_x, self.min_y, self.width, self.height = self.calc_bounds(root)
        self.lines = []
        self.zindex = 0
        
        gn = self.config.get('gui_name', 'ConvertedGui')
        mw = int(self.width * self.scale)
        mh = int(self.height * self.scale)
        
        self.w("local Players = game:GetService('Players')")
        self.w("local player = Players.LocalPlayer")
        self.w("local playerGui = player:WaitForChild('PlayerGui')")
        self.w("")
        self.w("local screenGui = Instance.new('ScreenGui')")
        self.w(f"screenGui.Name = '{gn}'")
        self.w("screenGui.ResetOnSpawn = false")
        self.w("screenGui.ZIndexBehavior = Enum.ZIndexBehavior.Sibling")
        self.w("screenGui.Parent = playerGui")
        self.w("")
        self.w("local main = Instance.new('Frame')")
        self.w("main.Name = 'Main'")
        self.w(f"main.Size = UDim2.new(0, {mw}, 0, {mh})")
        
        pos = self.config.get('position', 'center')
        pm = {
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
        if pos in pm:
            self.w(f"main.Position = {pm[pos][0]}")
            self.w(f"main.AnchorPoint = {pm[pos][1]}")
        else:
            self.w("main.Position = UDim2.new(0, 0, 0, 0)")
        
        self.w("main.BackgroundTransparency = 1")
        self.w("main.BorderSizePixel = 0")
        self.w("main.Parent = screenGui")
        self.w("")
        
        idx = 1
        for item in root.findall('Item'):
            self.write_element(item, f'el{idx}', 'main', True)
            idx += 1
        
        if self.config.get('draggable'):
            self.w("local UIS = game:GetService('UserInputService')")
            self.w("local dragging, dragInput, dragStart, startPos")
            self.w("main.InputBegan:Connect(function(input)")
            self.w("\tif input.UserInputType == Enum.UserInputType.MouseButton1 or input.UserInputType == Enum.UserInputType.Touch then")
            self.w("\t\tdragging = true")
            self.w("\t\tdragStart = input.Position")
            self.w("\t\tstartPos = main.Position")
            self.w("\t\tinput.Changed:Connect(function()")
            self.w("\t\t\tif input.UserInputState == Enum.UserInputState.End then dragging = false end")
            self.w("\t\tend)")
            self.w("\tend")
            self.w("end)")
            self.w("main.InputChanged:Connect(function(input)")
            self.w("\tif input.UserInputType == Enum.UserInputType.MouseMovement or input.UserInputType == Enum.UserInputType.Touch then")
            self.w("\t\tdragInput = input")
            self.w("\tend")
            self.w("end)")
            self.w("UIS.InputChanged:Connect(function(input)")
            self.w("\tif input == dragInput and dragging then")
            self.w("\t\tlocal delta = input.Position - dragStart")
            self.w("\t\tmain.Position = UDim2.new(startPos.X.Scale, startPos.X.Offset + delta.X, startPos.Y.Scale, startPos.Y.Offset + delta.Y)")
            self.w("\tend")
            self.w("end)")
            self.w("")
        
        dk = self.config.get('destroykey', 'none')
        km = {'x':'X','delete':'Delete','backspace':'Backspace','escape':'Escape','p':'P','m':'M','k':'K'}
        if dk in km:
            self.w(f"game:GetService('UserInputService').InputBegan:Connect(function(i,g)")
            self.w(f"\tif not g and i.KeyCode == Enum.KeyCode.{km[dk]} then screenGui:Destroy() end")
            self.w("end)")
        
        return '\n'.join(self.lines)

converter = UniversalConverter()

@bot.event
async def on_ready():
    print(f'{bot.user} connected!')

@bot.command(name='convert')
async def convert_cmd(ctx, drag='false', pos='center', scl: float=1.0, key='none', name='ConvertedGui'):
    if not ctx.message.attachments:
        await ctx.send("Attach .rbxmx file!")
        return
    att = ctx.message.attachments[0]
    if not att.filename.lower().endswith('.rbxmx'):
        await ctx.send("Use .rbxmx!")
        return
    try:
        data = await att.read()
        xml = data.decode('utf-8')
        d = drag.lower() == 'true'
        vp = ['center','top','bottom','left','right','topleft','topright','bottomleft','bottomright','original']
        p = pos.lower() if pos.lower() in vp else 'center'
        s = scl if 0.1 <= scl <= 5.0 else 1.0
        vk = ['none','x','delete','backspace','escape','p','m','k']
        k = key.lower() if key.lower() in vk else 'none'
        n = name.replace('_',' ')
        await ctx.send(f"Converting: drag={d} pos={p} scale={s} key={k}")
        converter.set_config(draggable=d, position=p, scale=s, destroykey=k, gui_name=n)
        lua = converter.convert(xml)
        f = discord.File(io.BytesIO(lua.encode('utf-8')), filename=att.filename.replace('.rbxmx','.lua'))
        await ctx.send("Done!", file=f)
    except Exception as e:
        await ctx.send(f"Error: {e}")

@bot.command(name='chelp')
async def chelp_cmd(ctx):
    e = discord.Embed(title="Commands", color=0x00ff00)
    e.add_field(name="!convert", value="Convert RBXMX to Lua", inline=False)
    e.add_field(name="!cconfig", value="Config options", inline=False)
    e.add_field(name="!ping", value="Bot status", inline=False)
    e.add_field(name="!example", value="Examples", inline=False)
    await ctx.send(embed=e)

@bot.command(name='cconfig')
async def cconfig_cmd(ctx):
    e = discord.Embed(title="Config", color=0x0000ff)
    e.add_field(name="Usage", value="`!convert [drag] [pos] [scale] [key] [name]`", inline=False)
    e.add_field(name="drag", value="true/false", inline=True)
    e.add_field(name="pos", value="center/top/bottom/left/right/topleft/topright/bottomleft/bottomright/original", inline=True)
    e.add_field(name="scale", value="0.1-5.0", inline=True)
    e.add_field(name="key", value="none/x/delete/backspace/escape/p/m/k", inline=True)
    e.add_field(name="name", value="GUI name (_ for spaces)", inline=True)
    await ctx.send(embed=e)

@bot.command(name='ping')
async def ping_cmd(ctx):
    await ctx.send(f"Pong! {round(bot.latency*1000)}ms")

@bot.command(name='example')
async def example_cmd(ctx):
    e = discord.Embed(title="Examples", color=0xff00ff)
    e.add_field(name="Basic", value="`!convert`", inline=False)
    e.add_field(name="Draggable", value="`!convert true center`", inline=False)
    e.add_field(name="Scaled", value="`!convert true topleft 1.5`", inline=False)
    e.add_field(name="Close key", value="`!convert true center 1.0 x`", inline=False)
    e.add_field(name="Full", value="`!convert true center 1.2 escape My_GUI`", inline=False)
    await ctx.send(embed=e)

async def main():
    await start_web_server()
    await bot.start(os.getenv('DISCORD_BOT_TOKEN'))

if __name__ == "__main__":
    if os.getenv('DISCORD_BOT_TOKEN'):
        asyncio.run(main())
    else:
        print("No token!")
