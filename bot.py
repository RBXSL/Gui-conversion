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

class SmartConverter:
    def __init__(self):
        self.lines = []
        self.config = {}
        self.scale = 1.0
        self.elements = []
        self.min_x = 0
        self.min_y = 0
        self.main_w = 0
        self.main_h = 0
        self.header_h = 0
        self.buttons = []
        self.header_el = None
        self.bg_el = None
        self.title_el = None

    def set_config(self, **kw):
        self.config = kw
        self.scale = kw.get('scale', 1.0)

    def w(self, line):
        self.lines.append(line)

    def parse_xml(self, xml_str):
        root = ET.fromstring(xml_str)
        self.elements = []
        for item in root.findall('Item'):
            el = self.parse_item(item)
            if el:
                self.elements.append(el)
        return self.elements

    def parse_item(self, item):
        cls = item.get('class')
        if not cls:
            return None
        props = item.find('Properties')
        data = {'class': cls, 'children': []}
        if props is not None:
            for p in props:
                name = p.get('name')
                tag = p.tag
                if tag == 'string':
                    data[name] = p.text or ''
                elif tag == 'bool':
                    data[name] = p.text == 'true'
                elif tag == 'int':
                    data[name] = int(p.text or 0)
                elif tag == 'float':
                    data[name] = float(p.text or 0)
                elif tag == 'token':
                    data[name] = int(p.text or 0)
                elif tag == 'Color3':
                    data[name] = {
                        'r': float(p.findtext('R') or 0),
                        'g': float(p.findtext('G') or 0),
                        'b': float(p.findtext('B') or 0)
                    }
                elif tag == 'UDim2':
                    data[name] = {
                        'xs': float(p.findtext('XS') or 0),
                        'xo': float(p.findtext('XO') or 0),
                        'ys': float(p.findtext('YS') or 0),
                        'yo': float(p.findtext('YO') or 0)
                    }
                elif tag == 'UDim':
                    data[name] = {
                        's': float(p.findtext('S') or 0),
                        'o': float(p.findtext('O') or 0)
                    }
                elif tag == 'Font':
                    fam = p.find('Family')
                    url = 'rbxasset://fonts/families/SourceSansPro.json'
                    if fam is not None:
                        u = fam.find('url')
                        if u is not None and u.text:
                            url = u.text
                    wgt = p.findtext('Weight') or '400'
                    sty = p.findtext('Style') or 'Normal'
                    wmap = {'100':'Thin','200':'ExtraLight','300':'Light','400':'Regular','500':'Medium','600':'SemiBold','700':'Bold','800':'ExtraBold','900':'Heavy'}
                    data[name] = {'url': url, 'weight': wmap.get(wgt, wgt), 'style': sty}
                elif tag == 'Content':
                    u = p.find('url')
                    data[name] = u.text if u is not None and u.text and u.text != 'undefined' else ''
        for child in item.findall('Item'):
            c = self.parse_item(child)
            if c:
                data['children'].append(c)
        return data

    def analyze_structure(self):
        if not self.elements:
            return
        
        sizes = []
        positions = []
        for el in self.elements:
            if 'Size' in el and 'Position' in el:
                sz = el['Size']
                ps = el['Position']
                area = sz['xo'] * sz['yo']
                sizes.append((area, el, sz, ps))
                positions.append(ps)
        
        if not sizes:
            return
        
        sizes.sort(key=lambda x: x[0], reverse=True)
        self.bg_el = sizes[0][1]
        self.main_w = sizes[0][2]['xo']
        self.main_h = sizes[0][2]['yo']
        self.min_x = sizes[0][3]['xo']
        self.min_y = sizes[0][3]['yo']
        
        for el in self.elements:
            cls = el.get('class', '')
            if cls == 'TextLabel' and 'Text' in el:
                if el.get('TextSize', 0) >= 24:
                    self.title_el = el
            elif cls == 'Frame' and 'BackgroundColor3' in el:
                sz = el.get('Size', {})
                if sz.get('xo', 0) < 200 and sz.get('yo', 0) < 100:
                    self.buttons.append(el)
        
        for el in self.elements:
            sz = el.get('Size', {})
            if sz.get('yo', 0) > 0 and sz.get('yo', 0) < 100 and sz.get('xo', 0) > 400:
                ps = el.get('Position', {})
                if abs(ps.get('yo', 0) - self.min_y) < 10:
                    self.header_el = el
                    self.header_h = sz.get('yo', 61)
                    break
        
        if not self.header_h:
            self.header_h = 61

    def generate(self):
        self.analyze_structure()
        self.lines = []
        
        gn = self.config.get('gui_name', 'ConvertedGui')
        mw = int(self.main_w * self.scale)
        mh = int(self.main_h * self.scale)
        hh = int(self.header_h * self.scale)
        
        bg_color = self.bg_el.get('BackgroundColor3', {'r': 0.25, 'g': 0.18, 'b': 0.18}) if self.bg_el else {'r': 0.25, 'g': 0.18, 'b': 0.18}
        bg_trans = self.bg_el.get('BackgroundTransparency', 0.25) if self.bg_el else 0.25
        if self.bg_el and self.bg_el.get('class') == 'ImageLabel':
            bg_trans = self.bg_el.get('ImageTransparency', 0.25)
        
        header_color = {'r': 0.2, 'g': 0.12, 'b': 0.12}
        if self.header_el and 'BackgroundColor3' in self.header_el:
            header_color = self.header_el['BackgroundColor3']
        
        title_text = "GUI"
        title_color = {'r': 1, 'g': 1, 'b': 1}
        title_size = 48
        title_font = {'url': 'rbxasset://fonts/families/SourceSansPro.json', 'weight': 'Regular', 'style': 'Normal'}
        title_stroke_color = {'r': 0.4, 'g': 0.2, 'b': 0.2}
        title_stroke_thickness = 4
        
        if self.title_el:
            title_text = self.title_el.get('Text', 'GUI')
            title_color = self.title_el.get('TextColor3', title_color)
            title_size = int(self.title_el.get('TextSize', 48) * self.scale)
            if 'FontFace' in self.title_el:
                title_font = self.title_el['FontFace']
            for child in self.title_el.get('children', []):
                if child.get('class') == 'UIStroke':
                    title_stroke_color = child.get('Color', title_stroke_color)
                    title_stroke_thickness = child.get('Thickness', 4) * self.scale
        
        btn_color = {'r': 0.326923, 'g': 0.223188, 'b': 0.223188}
        btn_stroke_color = {'r': 1, 'g': 0.572115, 'b': 0.572115}
        btn_stroke_thickness = 2
        btn_corner = 15
        btn_w = 137
        btn_h = 69
        
        if self.buttons:
            b = self.buttons[0]
            btn_color = b.get('BackgroundColor3', btn_color)
            sz = b.get('Size', {})
            btn_w = int(sz.get('xo', 137))
            btn_h = int(sz.get('yo', 69))
            for child in b.get('children', []):
                if child.get('class') == 'UIStroke':
                    btn_stroke_color = child.get('Color', btn_stroke_color)
                    btn_stroke_thickness = child.get('Thickness', 2)
                elif child.get('class') == 'UICorner':
                    cr = child.get('CornerRadius', {'s': 0, 'o': 15})
                    btn_corner = int(cr.get('o', 15))
        
        btn_w = int(btn_w * self.scale)
        btn_h = int(btn_h * self.scale)
        btn_corner = int(btn_corner * self.scale)
        btn_stroke_thickness = int(btn_stroke_thickness * self.scale)
        
        num_buttons = len(self.buttons) if self.buttons else 9
        if num_buttons < 9:
            num_buttons = 9
        
        cols = 3
        rows = (num_buttons + cols - 1) // cols
        
        container_top = hh + 12
        
        pad_x = 20
        pad_y = 20
        
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
        
        self.w("local bg = Instance.new('Frame')")
        self.w("bg.Name = 'Background'")
        self.w("bg.Size = UDim2.new(1, 0, 1, 0)")
        self.w("bg.Position = UDim2.new(0, 0, 0, 0)")
        self.w(f"bg.BackgroundColor3 = Color3.new({bg_color['r']}, {bg_color['g']}, {bg_color['b']})")
        self.w(f"bg.BackgroundTransparency = {bg_trans}")
        self.w("bg.BorderSizePixel = 0")
        self.w("bg.ZIndex = 1")
        self.w("bg.Parent = main")
        self.w("")
        self.w("local bgCorner = Instance.new('UICorner')")
        self.w("bgCorner.CornerRadius = UDim.new(0, 15)")
        self.w("bgCorner.Parent = bg")
        self.w("")
        
        self.w("local header = Instance.new('Frame')")
        self.w("header.Name = 'Header'")
        self.w(f"header.Size = UDim2.new(1, 0, 0, {hh})")
        self.w("header.Position = UDim2.new(0, 0, 0, 0)")
        self.w(f"header.BackgroundColor3 = Color3.new({header_color['r']}, {header_color['g']}, {header_color['b']})")
        self.w("header.BackgroundTransparency = 0")
        self.w("header.BorderSizePixel = 0")
        self.w("header.ZIndex = 2")
        self.w("header.Parent = main")
        self.w("")
        self.w("local headerCorner = Instance.new('UICorner')")
        self.w("headerCorner.CornerRadius = UDim.new(0, 15)")
        self.w("headerCorner.Parent = header")
        self.w("")
        
        title_text_escaped = title_text.replace('\\', '\\\\').replace('"', '\\"')
        self.w("local title = Instance.new('TextLabel')")
        self.w("title.Name = 'Title'")
        self.w("title.Size = UDim2.new(1, 0, 1, 0)")
        self.w("title.Position = UDim2.new(0, 0, 0, 0)")
        self.w("title.BackgroundTransparency = 1")
        self.w(f'title.Text = "{title_text_escaped}"')
        self.w(f"title.TextColor3 = Color3.new({title_color['r']}, {title_color['g']}, {title_color['b']})")
        self.w(f"title.TextSize = {title_size}")
        self.w(f'title.FontFace = Font.new("{title_font["url"]}", Enum.FontWeight.{title_font["weight"]}, Enum.FontStyle.{title_font["style"]})')
        self.w("title.TextXAlignment = Enum.TextXAlignment.Center")
        self.w("title.TextYAlignment = Enum.TextYAlignment.Center")
        self.w("title.ZIndex = 3")
        self.w("title.Parent = header")
        self.w("")
        self.w("local titleStroke = Instance.new('UIStroke')")
        self.w(f"titleStroke.Color = Color3.new({title_stroke_color['r']}, {title_stroke_color['g']}, {title_stroke_color['b']})")
        self.w(f"titleStroke.Thickness = {title_stroke_thickness}")
        self.w("titleStroke.Parent = title")
        self.w("")
        
        self.w("local buttonContainer = Instance.new('Frame')")
        self.w("buttonContainer.Name = 'Buttons'")
        self.w(f"buttonContainer.Size = UDim2.new(1, -24, 1, -{container_top + 12})")
        self.w(f"buttonContainer.Position = UDim2.new(0, 12, 0, {container_top})")
        self.w("buttonContainer.BackgroundTransparency = 1")
        self.w("buttonContainer.BorderSizePixel = 0")
        self.w("buttonContainer.ZIndex = 2")
        self.w("buttonContainer.Parent = main")
        self.w("")
        self.w("local grid = Instance.new('UIGridLayout')")
        self.w(f"grid.CellSize = UDim2.new(0, {btn_w}, 0, {btn_h})")
        self.w(f"grid.CellPadding = UDim2.new(0, {pad_x}, 0, {pad_y})")
        self.w("grid.SortOrder = Enum.SortOrder.LayoutOrder")
        self.w("grid.Parent = buttonContainer")
        self.w("")
        
        self.w(f"for i = 1, {num_buttons} do")
        self.w("\tlocal btn = Instance.new('Frame')")
        self.w('\tbtn.Name = "Button" .. i')
        self.w(f"\tbtn.BackgroundColor3 = Color3.new({btn_color['r']}, {btn_color['g']}, {btn_color['b']})")
        self.w("\tbtn.BackgroundTransparency = 0")
        self.w("\tbtn.BorderSizePixel = 0")
        self.w("\tbtn.LayoutOrder = i")
        self.w("\tbtn.ZIndex = 3")
        self.w("\tbtn.Parent = buttonContainer")
        self.w("")
        self.w("\tlocal stroke = Instance.new('UIStroke')")
        self.w(f"\tstroke.Color = Color3.new({btn_stroke_color['r']}, {btn_stroke_color['g']}, {btn_stroke_color['b']})")
        self.w(f"\tstroke.Thickness = {btn_stroke_thickness}")
        self.w("\tstroke.Parent = btn")
        self.w("")
        self.w("\tlocal corner = Instance.new('UICorner')")
        self.w(f"\tcorner.CornerRadius = UDim.new(0, {btn_corner})")
        self.w("\tcorner.Parent = btn")
        self.w("end")
        self.w("")
        
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

    def convert(self, xml_str):
        try:
            self.parse_xml(xml_str)
            return self.generate()
        except ET.ParseError as e:
            return f'-- XML Error: {e}'
        except Exception as e:
            return f'-- Error: {e}'

converter = SmartConverter()

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
