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
        self.scale = 1.0
        self.min_x = 0
        self.min_y = 0
        self.max_x = 0
        self.max_y = 0

    def set_config(self, **kw):
        self.config = kw
        self.scale = kw.get('scale', 1.0)

    def w(self, line):
        self.lines.append(line)

    def get_udim2(self, props, name):
        for p in props:
            if p.get('name') == name and p.tag == 'UDim2':
                xs = float(p.findtext('XS') or 0)
                xo = float(p.findtext('XO') or 0)
                ys = float(p.findtext('YS') or 0)
                yo = float(p.findtext('YO') or 0)
                return xs, xo, ys, yo
        return 0, 0, 0, 0

    def get_udim(self, props, name):
        for p in props:
            if p.get('name') == name and p.tag == 'UDim':
                s = float(p.findtext('S') or 0)
                o = float(p.findtext('O') or 0)
                return s, o
        return 0, 0

    def get_color3(self, props, name):
        for p in props:
            if p.get('name') == name and p.tag == 'Color3':
                r = p.findtext('R') or '0'
                g = p.findtext('G') or '0'
                b = p.findtext('B') or '0'
                return r, g, b
        return None

    def get_str(self, props, name):
        for p in props:
            if p.get('name') == name and p.tag == 'string':
                return p.text or ''
        return None

    def get_float(self, props, name):
        for p in props:
            if p.get('name') == name and p.tag == 'float':
                return p.text or '0'
        return None

    def get_int(self, props, name):
        for p in props:
            if p.get('name') == name and p.tag == 'int':
                return p.text or '0'
        return None

    def get_bool(self, props, name):
        for p in props:
            if p.get('name') == name and p.tag == 'bool':
                return p.text or 'false'
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
                wgt = p.find('Weight')
                sty = p.find('Style')
                url = 'rbxasset://fonts/families/SourceSansPro.json'
                wv, sv = 'Regular', 'Normal'
                if fam is not None:
                    u = fam.find('url')
                    if u is not None and u.text:
                        url = u.text
                if wgt is not None and wgt.text:
                    wmap = {'100':'Thin','200':'ExtraLight','300':'Light','400':'Regular','500':'Medium','600':'SemiBold','700':'Bold','800':'ExtraBold','900':'Heavy'}
                    wv = wmap.get(wgt.text, wgt.text)
                if sty is not None and sty.text:
                    sv = sty.text
                return url, wv, sv
        return None

    def get_content(self, props, name):
        for p in props:
            if p.get('name') == name and p.tag == 'Content':
                u = p.find('url')
                if u is not None and u.text and u.text != 'undefined':
                    return u.text
        return None

    def calc_bounds(self, root):
        all_x = []
        all_y = []
        all_right = []
        all_bottom = []
        
        for item in root.findall('Item'):
            props = item.find('Properties')
            if props is None:
                continue
            _, xo, _, yo = self.get_udim2(props, 'Position')
            _, sw, _, sh = self.get_udim2(props, 'Size')
            all_x.append(xo)
            all_y.append(yo)
            all_right.append(xo + sw)
            all_bottom.append(yo + sh)
        
        if not all_x:
            return
        
        self.min_x = min(all_x)
        self.min_y = min(all_y)
        self.max_x = max(all_right)
        self.max_y = max(all_bottom)

    def enum_str(self, name, val):
        maps = {
            'ApplyStrokeMode': {0: 'Enum.ApplyStrokeMode.Contextual', 1: 'Enum.ApplyStrokeMode.Border'},
            'LineJoinMode': {0: 'Enum.LineJoinMode.Round', 1: 'Enum.LineJoinMode.Bevel', 2: 'Enum.LineJoinMode.Miter'},
            'TextXAlignment': {0: 'Enum.TextXAlignment.Center', 1: 'Enum.TextXAlignment.Left', 2: 'Enum.TextXAlignment.Right'},
            'TextYAlignment': {0: 'Enum.TextYAlignment.Center', 1: 'Enum.TextYAlignment.Top', 2: 'Enum.TextYAlignment.Bottom'},
            'AutomaticSize': {0: 'Enum.AutomaticSize.None', 1: 'Enum.AutomaticSize.X', 2: 'Enum.AutomaticSize.Y', 3: 'Enum.AutomaticSize.XY'},
        }
        if name in maps and val in maps[name]:
            return maps[name][val]
        return str(val)

    def write_ui_element(self, item, var, parent):
        cls = item.get('class')
        if not cls:
            return
        
        props = item.find('Properties')
        self.w(f"local {var} = Instance.new('{cls}')")
        
        if props is not None:
            nm = self.get_str(props, 'Name')
            if nm:
                nm = nm.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '')
                self.w(f'{var}.Name = "{nm}"')
            
            c = self.get_color3(props, 'Color')
            if c:
                self.w(f'{var}.Color = Color3.new({c[0]}, {c[1]}, {c[2]})')
            
            t = self.get_float(props, 'Transparency')
            if t is not None:
                self.w(f'{var}.Transparency = {t}')
            
            th = self.get_float(props, 'Thickness')
            if th is not None:
                self.w(f'{var}.Thickness = {th}')
            
            asm = self.get_token(props, 'ApplyStrokeMode')
            if asm is not None:
                self.w(f'{var}.ApplyStrokeMode = {self.enum_str("ApplyStrokeMode", asm)}')
            
            ljm = self.get_token(props, 'LineJoinMode')
            if ljm is not None:
                self.w(f'{var}.LineJoinMode = {self.enum_str("LineJoinMode", ljm)}')
            
            crs, cro = self.get_udim(props, 'CornerRadius')
            if cro != 0 or crs != 0:
                self.w(f'{var}.CornerRadius = UDim.new({crs}, {int(cro)})')
        
        self.w(f'{var}.Parent = {parent}')
        self.w('')
        
        ci = 1
        for child in item.findall('Item'):
            self.write_ui_element(child, f'{var}_{ci}', var)
            ci += 1

    def write_gui_element(self, item, var, parent, apply_offset):
        cls = item.get('class')
        if not cls:
            return
        
        props = item.find('Properties')
        self.w(f"local {var} = Instance.new('{cls}')")
        
        if props is not None:
            nm = self.get_str(props, 'Name')
            if nm:
                nm = nm.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '')
                self.w(f'{var}.Name = "{nm}"')
            
            xs, xo, ys, yo = self.get_udim2(props, 'Size')
            nxo = int(xo * self.scale)
            nyo = int(yo * self.scale)
            self.w(f'{var}.Size = UDim2.new({xs}, {nxo}, {ys}, {nyo})')
            
            pxs, pxo, pys, pyo = self.get_udim2(props, 'Position')
            if apply_offset:
                npxo = int((pxo - self.min_x) * self.scale)
                npyo = int((pyo - self.min_y) * self.scale)
            else:
                npxo = int(pxo * self.scale)
                npyo = int(pyo * self.scale)
            self.w(f'{var}.Position = UDim2.new({pxs}, {npxo}, {pys}, {npyo})')
            
            bc = self.get_color3(props, 'BackgroundColor3')
            if bc:
                self.w(f'{var}.BackgroundColor3 = Color3.new({bc[0]}, {bc[1]}, {bc[2]})')
            
            bt = self.get_float(props, 'BackgroundTransparency')
            if bt is not None:
                self.w(f'{var}.BackgroundTransparency = {bt}')
            
            bs = self.get_int(props, 'BorderSizePixel')
            if bs is not None:
                self.w(f'{var}.BorderSizePixel = {bs}')
            
            vis = self.get_bool(props, 'Visible')
            if vis is not None:
                self.w(f'{var}.Visible = {vis}')
            
            tc = self.get_color3(props, 'TextColor3')
            if tc:
                self.w(f'{var}.TextColor3 = Color3.new({tc[0]}, {tc[1]}, {tc[2]})')
            
            tt = self.get_float(props, 'TextTransparency')
            if tt is not None:
                self.w(f'{var}.TextTransparency = {tt}')
            
            tsz = self.get_int(props, 'TextSize')
            if tsz is not None:
                self.w(f'{var}.TextSize = {tsz}')
            
            txt = self.get_str(props, 'Text')
            if txt is not None:
                txt = txt.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '')
                self.w(f'{var}.Text = "{txt}"')
            
            tw = self.get_bool(props, 'TextWrapped')
            if tw is not None:
                self.w(f'{var}.TextWrapped = {tw}')
            
            txa = self.get_token(props, 'TextXAlignment')
            if txa is not None:
                self.w(f'{var}.TextXAlignment = {self.enum_str("TextXAlignment", txa)}')
            
            tya = self.get_token(props, 'TextYAlignment')
            if tya is not None:
                self.w(f'{var}.TextYAlignment = {self.enum_str("TextYAlignment", tya)}')
            
            aus = self.get_token(props, 'AutomaticSize')
            if aus is not None:
                self.w(f'{var}.AutomaticSize = {self.enum_str("AutomaticSize", aus)}')
            
            font = self.get_font(props, 'FontFace')
            if font:
                self.w(f'{var}.FontFace = Font.new("{font[0]}", Enum.FontWeight.{font[1]}, Enum.FontStyle.{font[2]})')
            
            img = self.get_content(props, 'Image')
            if img:
                self.w(f'{var}.Image = "{img}"')
            
            it = self.get_float(props, 'ImageTransparency')
            if it is not None:
                self.w(f'{var}.ImageTransparency = {it}')
        
        self.w(f'{var}.Parent = {parent}')
        self.w('')
        
        ci = 1
        for child in item.findall('Item'):
            child_cls = child.get('class')
            if child_cls in ['UIStroke', 'UICorner', 'UIGradient', 'UIListLayout', 'UIGridLayout', 'UIPadding', 'UIAspectRatioConstraint', 'UISizeConstraint', 'UIScale']:
                self.write_ui_element(child, f'{var}_{ci}', var)
            else:
                self.write_gui_element(child, f'{var}_{ci}', var, False)
            ci += 1

    def convert(self, xml_str):
        try:
            root = ET.fromstring(xml_str)
        except ET.ParseError as e:
            return f'-- Error: {e}'
        
        self.calc_bounds(root)
        
        width = int((self.max_x - self.min_x) * self.scale)
        height = int((self.max_y - self.min_y) * self.scale)
        gn = self.config.get('gui_name', 'ConvertedGui')
        
        self.lines = []
        
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
        self.w(f"main.Size = UDim2.new(0, {width}, 0, {height})")
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
            self.write_gui_element(item, f'el{idx}', 'main', True)
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
