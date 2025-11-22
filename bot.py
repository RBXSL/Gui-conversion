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

class Converter:
    def __init__(self):
        self.lines = []
        self.config = {}
        self.min_x = 0
        self.min_y = 0
        self.main_w = 0
        self.main_h = 0
        self.scale = 1.0
        self.enums = {
            'ApplyStrokeMode': {0: 'Enum.ApplyStrokeMode.Contextual', 1: 'Enum.ApplyStrokeMode.Border'},
            'LineJoinMode': {0: 'Enum.LineJoinMode.Round', 1: 'Enum.LineJoinMode.Bevel', 2: 'Enum.LineJoinMode.Miter'},
            'AutomaticSize': {0: 'Enum.AutomaticSize.None', 1: 'Enum.AutomaticSize.X', 2: 'Enum.AutomaticSize.Y', 3: 'Enum.AutomaticSize.XY'},
            'TextXAlignment': {0: 'Enum.TextXAlignment.Center', 1: 'Enum.TextXAlignment.Left', 2: 'Enum.TextXAlignment.Right'},
            'TextYAlignment': {0: 'Enum.TextYAlignment.Center', 1: 'Enum.TextYAlignment.Top', 2: 'Enum.TextYAlignment.Bottom'},
            'ScaleType': {0: 'Enum.ScaleType.Stretch', 1: 'Enum.ScaleType.Slice', 2: 'Enum.ScaleType.Tile', 3: 'Enum.ScaleType.Fit', 4: 'Enum.ScaleType.Crop'},
            'FillDirection': {0: 'Enum.FillDirection.Horizontal', 1: 'Enum.FillDirection.Vertical'},
            'HorizontalAlignment': {0: 'Enum.HorizontalAlignment.Center', 1: 'Enum.HorizontalAlignment.Left', 2: 'Enum.HorizontalAlignment.Right'},
            'VerticalAlignment': {0: 'Enum.VerticalAlignment.Center', 1: 'Enum.VerticalAlignment.Top', 2: 'Enum.VerticalAlignment.Bottom'},
            'SortOrder': {0: 'Enum.SortOrder.Name', 1: 'Enum.SortOrder.Custom', 2: 'Enum.SortOrder.LayoutOrder'},
        }

    def set_config(self, **kw):
        self.config = kw
        self.scale = kw.get('scale', 1.0)

    def get_props(self, item):
        return item.find('Properties')

    def read_udim2(self, props, name):
        if props is None:
            return 0, 0, 0, 0
        for p in props:
            if p.get('name') == name and p.tag == 'UDim2':
                return (
                    float(p.findtext('XS') or 0),
                    float(p.findtext('XO') or 0),
                    float(p.findtext('YS') or 0),
                    float(p.findtext('YO') or 0)
                )
        return 0, 0, 0, 0

    def find_main_container(self, root):
        largest = None
        largest_area = 0
        for item in root.findall('Item'):
            props = self.get_props(item)
            _, sw, _, sh = self.read_udim2(props, 'Size')
            area = sw * sh
            if area > largest_area:
                largest_area = area
                largest = item
                self.main_w = sw
                self.main_h = sh
        if largest is not None:
            props = self.get_props(largest)
            _, self.min_x, _, self.min_y = self.read_udim2(props, 'Position')
        return largest

    def w(self, line):
        self.lines.append(line)

    def process_child(self, item, var, parent):
        cls = item.get('class')
        if not cls:
            return
        props = self.get_props(item)
        self.w(f"local {var} = Instance.new('{cls}')")
        
        if props:
            for p in props:
                nm = p.get('name')
                if nm == 'Name' and p.tag == 'string':
                    t = (p.text or '').replace('\\', '\\\\').replace('"', '\\"').replace('\n', '')
                    self.w(f'{var}.Name = "{t}"')
                elif nm == 'Size' and p.tag == 'UDim2':
                    xs, xo, ys, yo = self.read_udim2(props, 'Size')
                    self.w(f'{var}.Size = UDim2.new({xs}, {int(xo * self.scale)}, {ys}, {int(yo * self.scale)})')
                elif nm == 'Position' and p.tag == 'UDim2':
                    xs, xo, ys, yo = self.read_udim2(props, 'Position')
                    self.w(f'{var}.Position = UDim2.new({xs}, {int(xo * self.scale)}, {ys}, {int(yo * self.scale)})')
                elif nm == 'BackgroundColor3' and p.tag == 'Color3':
                    r, g, b = p.findtext('R') or 0, p.findtext('G') or 0, p.findtext('B') or 0
                    self.w(f'{var}.BackgroundColor3 = Color3.new({r}, {g}, {b})')
                elif nm == 'BackgroundTransparency' and p.tag == 'float':
                    self.w(f'{var}.BackgroundTransparency = {p.text or 0}')
                elif nm == 'BorderSizePixel' and p.tag == 'int':
                    self.w(f'{var}.BorderSizePixel = {p.text or 0}')
                elif nm == 'Visible' and p.tag == 'bool':
                    self.w(f'{var}.Visible = {p.text or "true"}')
                elif nm == 'Color' and p.tag == 'Color3':
                    r, g, b = p.findtext('R') or 0, p.findtext('G') or 0, p.findtext('B') or 0
                    self.w(f'{var}.Color = Color3.new({r}, {g}, {b})')
                elif nm == 'Transparency' and p.tag == 'float':
                    self.w(f'{var}.Transparency = {p.text or 0}')
                elif nm == 'Thickness' and p.tag == 'float':
                    self.w(f'{var}.Thickness = {p.text or 1}')
                elif nm == 'ApplyStrokeMode' and p.tag == 'token':
                    v = int(p.text or 0)
                    self.w(f'{var}.ApplyStrokeMode = {self.enums["ApplyStrokeMode"].get(v, v)}')
                elif nm == 'LineJoinMode' and p.tag == 'token':
                    v = int(p.text or 0)
                    self.w(f'{var}.LineJoinMode = {self.enums["LineJoinMode"].get(v, v)}')
                elif nm == 'CornerRadius' and p.tag == 'UDim':
                    s = p.findtext('S') or 0
                    o = p.findtext('O') or 0
                    self.w(f'{var}.CornerRadius = UDim.new({s}, {int(float(o))})')
                elif nm == 'TextColor3' and p.tag == 'Color3':
                    r, g, b = p.findtext('R') or 0, p.findtext('G') or 0, p.findtext('B') or 0
                    self.w(f'{var}.TextColor3 = Color3.new({r}, {g}, {b})')
                elif nm == 'TextTransparency' and p.tag == 'float':
                    self.w(f'{var}.TextTransparency = {p.text or 0}')
                elif nm == 'TextSize' and p.tag == 'int':
                    self.w(f'{var}.TextSize = {p.text or 14}')
                elif nm == 'Text' and p.tag == 'string':
                    t = (p.text or '').replace('\\', '\\\\').replace('"', '\\"').replace('\n', '')
                    self.w(f'{var}.Text = "{t}"')
                elif nm == 'TextWrapped' and p.tag == 'bool':
                    self.w(f'{var}.TextWrapped = {p.text or "false"}')
                elif nm == 'TextXAlignment' and p.tag == 'token':
                    v = int(p.text or 0)
                    self.w(f'{var}.TextXAlignment = {self.enums["TextXAlignment"].get(v, v)}')
                elif nm == 'TextYAlignment' and p.tag == 'token':
                    v = int(p.text or 0)
                    self.w(f'{var}.TextYAlignment = {self.enums["TextYAlignment"].get(v, v)}')
                elif nm == 'AutomaticSize' and p.tag == 'token':
                    v = int(p.text or 0)
                    self.w(f'{var}.AutomaticSize = {self.enums["AutomaticSize"].get(v, v)}')
                elif nm == 'FontFace' and p.tag == 'Font':
                    fam = p.find('Family')
                    wgt = p.find('Weight')
                    sty = p.find('Style')
                    url = 'rbxasset://fonts/families/SourceSansPro.json'
                    wv = 'Regular'
                    sv = 'Normal'
                    if fam is not None:
                        u = fam.find('url')
                        if u is not None and u.text:
                            url = u.text
                    if wgt is not None and wgt.text:
                        wmap = {'100':'Thin','200':'ExtraLight','300':'Light','400':'Regular','500':'Medium','600':'SemiBold','700':'Bold','800':'ExtraBold','900':'Heavy'}
                        wv = wmap.get(wgt.text, wgt.text)
                    if sty is not None and sty.text:
                        sv = sty.text
                    self.w(f'{var}.FontFace = Font.new("{url}", Enum.FontWeight.{wv}, Enum.FontStyle.{sv})')
                elif nm == 'Image' and p.tag == 'Content':
                    u = p.find('url')
                    if u is not None and u.text and u.text != 'undefined':
                        self.w(f'{var}.Image = "{u.text}"')
                elif nm == 'ImageTransparency' and p.tag == 'float':
                    self.w(f'{var}.ImageTransparency = {p.text or 0}')
        
        self.w(f'{var}.Parent = {parent}')
        self.w('')
        
        ci = 1
        for child in item.findall('Item'):
            self.process_child(child, f'{var}_{ci}', var)
            ci += 1

    def process_top_level(self, item, var, parent):
        cls = item.get('class')
        if not cls:
            return
        props = self.get_props(item)
        self.w(f"local {var} = Instance.new('{cls}')")
        
        if props:
            for p in props:
                nm = p.get('name')
                if nm == 'Name' and p.tag == 'string':
                    t = (p.text or '').replace('\\', '\\\\').replace('"', '\\"').replace('\n', '')
                    self.w(f'{var}.Name = "{t}"')
                elif nm == 'Size' and p.tag == 'UDim2':
                    xs, xo, ys, yo = self.read_udim2(props, 'Size')
                    self.w(f'{var}.Size = UDim2.new({xs}, {int(xo * self.scale)}, {ys}, {int(yo * self.scale)})')
                elif nm == 'Position' and p.tag == 'UDim2':
                    xs, xo, ys, yo = self.read_udim2(props, 'Position')
                    nx = int((xo - self.min_x) * self.scale)
                    ny = int((yo - self.min_y) * self.scale)
                    self.w(f'{var}.Position = UDim2.new({xs}, {nx}, {ys}, {ny})')
                elif nm == 'BackgroundColor3' and p.tag == 'Color3':
                    r, g, b = p.findtext('R') or 0, p.findtext('G') or 0, p.findtext('B') or 0
                    self.w(f'{var}.BackgroundColor3 = Color3.new({r}, {g}, {b})')
                elif nm == 'BackgroundTransparency' and p.tag == 'float':
                    self.w(f'{var}.BackgroundTransparency = {p.text or 0}')
                elif nm == 'BorderSizePixel' and p.tag == 'int':
                    self.w(f'{var}.BorderSizePixel = {p.text or 0}')
                elif nm == 'Visible' and p.tag == 'bool':
                    self.w(f'{var}.Visible = {p.text or "true"}')
                elif nm == 'Color' and p.tag == 'Color3':
                    r, g, b = p.findtext('R') or 0, p.findtext('G') or 0, p.findtext('B') or 0
                    self.w(f'{var}.Color = Color3.new({r}, {g}, {b})')
                elif nm == 'Transparency' and p.tag == 'float':
                    self.w(f'{var}.Transparency = {p.text or 0}')
                elif nm == 'Thickness' and p.tag == 'float':
                    self.w(f'{var}.Thickness = {p.text or 1}')
                elif nm == 'ApplyStrokeMode' and p.tag == 'token':
                    v = int(p.text or 0)
                    self.w(f'{var}.ApplyStrokeMode = {self.enums["ApplyStrokeMode"].get(v, v)}')
                elif nm == 'LineJoinMode' and p.tag == 'token':
                    v = int(p.text or 0)
                    self.w(f'{var}.LineJoinMode = {self.enums["LineJoinMode"].get(v, v)}')
                elif nm == 'CornerRadius' and p.tag == 'UDim':
                    s = p.findtext('S') or 0
                    o = p.findtext('O') or 0
                    self.w(f'{var}.CornerRadius = UDim.new({s}, {int(float(o))})')
                elif nm == 'TextColor3' and p.tag == 'Color3':
                    r, g, b = p.findtext('R') or 0, p.findtext('G') or 0, p.findtext('B') or 0
                    self.w(f'{var}.TextColor3 = Color3.new({r}, {g}, {b})')
                elif nm == 'TextTransparency' and p.tag == 'float':
                    self.w(f'{var}.TextTransparency = {p.text or 0}')
                elif nm == 'TextSize' and p.tag == 'int':
                    self.w(f'{var}.TextSize = {p.text or 14}')
                elif nm == 'Text' and p.tag == 'string':
                    t = (p.text or '').replace('\\', '\\\\').replace('"', '\\"').replace('\n', '')
                    self.w(f'{var}.Text = "{t}"')
                elif nm == 'TextWrapped' and p.tag == 'bool':
                    self.w(f'{var}.TextWrapped = {p.text or "false"}')
                elif nm == 'TextXAlignment' and p.tag == 'token':
                    v = int(p.text or 0)
                    self.w(f'{var}.TextXAlignment = {self.enums["TextXAlignment"].get(v, v)}')
                elif nm == 'TextYAlignment' and p.tag == 'token':
                    v = int(p.text or 0)
                    self.w(f'{var}.TextYAlignment = {self.enums["TextYAlignment"].get(v, v)}')
                elif nm == 'AutomaticSize' and p.tag == 'token':
                    v = int(p.text or 0)
                    self.w(f'{var}.AutomaticSize = {self.enums["AutomaticSize"].get(v, v)}')
                elif nm == 'FontFace' and p.tag == 'Font':
                    fam = p.find('Family')
                    wgt = p.find('Weight')
                    sty = p.find('Style')
                    url = 'rbxasset://fonts/families/SourceSansPro.json'
                    wv = 'Regular'
                    sv = 'Normal'
                    if fam is not None:
                        u = fam.find('url')
                        if u is not None and u.text:
                            url = u.text
                    if wgt is not None and wgt.text:
                        wmap = {'100':'Thin','200':'ExtraLight','300':'Light','400':'Regular','500':'Medium','600':'SemiBold','700':'Bold','800':'ExtraBold','900':'Heavy'}
                        wv = wmap.get(wgt.text, wgt.text)
                    if sty is not None and sty.text:
                        sv = sty.text
                    self.w(f'{var}.FontFace = Font.new("{url}", Enum.FontWeight.{wv}, Enum.FontStyle.{sv})')
                elif nm == 'Image' and p.tag == 'Content':
                    u = p.find('url')
                    if u is not None and u.text and u.text != 'undefined':
                        self.w(f'{var}.Image = "{u.text}"')
                elif nm == 'ImageTransparency' and p.tag == 'float':
                    self.w(f'{var}.ImageTransparency = {p.text or 0}')
        
        self.w(f'{var}.Parent = {parent}')
        self.w('')
        
        ci = 1
        for child in item.findall('Item'):
            self.process_child(child, f'{var}_{ci}', var)
            ci += 1

    def convert(self, xml_str):
        try:
            root = ET.fromstring(xml_str)
        except ET.ParseError as e:
            return f'-- Parse error: {e}'
        
        main_item = self.find_main_container(root)
        if main_item is None:
            return '-- No elements found'
        
        self.lines = []
        gn = self.config.get('gui_name', 'ConvertedGui')
        cw = int(self.main_w * self.scale)
        ch = int(self.main_h * self.scale)
        
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
        self.w(f"main.Size = UDim2.new(0, {cw}, 0, {ch})")
        self.w("main.BackgroundTransparency = 1")
        self.w("main.BorderSizePixel = 0")
        
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
        
        self.w("main.Parent = screenGui")
        self.w("")
        
        idx = 1
        for item in root.findall('Item'):
            self.process_top_level(item, f'el{idx}', 'main')
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

converter = Converter()

@bot.event
async def on_ready():
    print(f'{bot.user} connected!')

@bot.command(name='convert')
async def convert_cmd(ctx, drag='false', pos='center', scl: float=1.0, key='none', name='ConvertedGui', trans: float=-1):
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
        t = trans if 0 <= trans <= 1 else None
        await ctx.send(f"Converting: drag={d} pos={p} scale={s} key={k}")
        converter.set_config(draggable=d, position=p, scale=s, destroykey=k, gui_name=n, transparency=t)
        lua = converter.convert(xml)
        f = discord.File(io.BytesIO(lua.encode('utf-8')), filename=att.filename.replace('.rbxmx','.lua'))
        await ctx.send("Done!", file=f)
    except Exception as e:
        await ctx.send(f"Error: {e}")

@bot.command(name='chelp')
async def chelp_cmd(ctx):
    e = discord.Embed(title="Commands", color=0x00ff00)
    e.add_field(name="!convert", value="Convert RBXMX", inline=False)
    e.add_field(name="!cconfig", value="Config help", inline=False)
    e.add_field(name="!ping", value="Status", inline=False)
    e.add_field(name="!example", value="Examples", inline=False)
    await ctx.send(embed=e)

@bot.command(name='cconfig')
async def cconfig_cmd(ctx):
    e = discord.Embed(title="Config", color=0x0000ff)
    e.add_field(name="Usage", value="`!convert [drag] [pos] [scale] [key] [name] [trans]`", inline=False)
    e.add_field(name="drag", value="true/false", inline=True)
    e.add_field(name="pos", value="center/top/bottom/topleft/topright/bottomleft/bottomright/original", inline=True)
    e.add_field(name="scale", value="0.1-5.0", inline=True)
    e.add_field(name="key", value="none/x/delete/backspace/escape/p/m/k", inline=True)
    e.add_field(name="name", value="Text (_ = space)", inline=True)
    e.add_field(name="trans", value="0.0-1.0", inline=True)
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
    e.add_field(name="Full", value="`!convert true center 1.2 escape My_GUI 0.3`", inline=False)
    await ctx.send(embed=e)

async def main():
    await start_web_server()
    await bot.start(os.getenv('DISCORD_BOT_TOKEN'))

if __name__ == "__main__":
    if os.getenv('DISCORD_BOT_TOKEN'):
        asyncio.run(main())
    else:
        print("No token!")
