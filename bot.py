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
        self.lua_lines = []
        self.min_x = 0
        self.min_y = 0
        self.total_w = 0
        self.total_h = 0
        self.scale = 1.0
        self.config = {}
        self.enum_map = {
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
    
    def set_config(self, **kwargs):
        self.config = kwargs
        self.scale = kwargs.get('scale', 1.0)

    def read_udim2(self, props, name):
        for p in props:
            if p.get('name') == name and p.tag == 'UDim2':
                xs = float(p.findtext('XS') or 0)
                xo = float(p.findtext('XO') or 0)
                ys = float(p.findtext('YS') or 0)
                yo = float(p.findtext('YO') or 0)
                return xs, xo, ys, yo
        return 0, 0, 0, 0

    def read_udim(self, props, name):
        for p in props:
            if p.get('name') == name and p.tag == 'UDim':
                s = float(p.findtext('S') or 0)
                o = float(p.findtext('O') or 0)
                return s, o
        return 0, 0

    def read_color3(self, props, name):
        for p in props:
            if p.get('name') == name and p.tag == 'Color3':
                r = p.findtext('R') or '0'
                g = p.findtext('G') or '0'
                b = p.findtext('B') or '0'
                return f"Color3.new({r}, {g}, {b})"
        return None

    def read_string(self, props, name):
        for p in props:
            if p.get('name') == name and p.tag == 'string':
                txt = p.text or ''
                txt = txt.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
                return f'"{txt}"'
        return None

    def read_bool(self, props, name):
        for p in props:
            if p.get('name') == name and p.tag == 'bool':
                return p.text or 'false'
        return None

    def read_int(self, props, name):
        for p in props:
            if p.get('name') == name and p.tag == 'int':
                return p.text or '0'
        return None

    def read_float(self, props, name):
        for p in props:
            if p.get('name') == name and p.tag == 'float':
                return p.text or '0'
        return None

    def read_token(self, props, name):
        for p in props:
            if p.get('name') == name and p.tag == 'token':
                val = int(p.text or 0)
                if name in self.enum_map and val in self.enum_map[name]:
                    return self.enum_map[name][val]
                return str(val)
        return None

    def read_font(self, props, name):
        for p in props:
            if p.get('name') == name and p.tag == 'Font':
                fam = p.find('Family')
                wgt = p.find('Weight')
                sty = p.find('Style')
                url = 'rbxasset://fonts/families/SourceSansPro.json'
                w = 'Regular'
                s = 'Normal'
                if fam is not None:
                    u = fam.find('url')
                    if u is not None and u.text:
                        url = u.text
                if wgt is not None and wgt.text:
                    wmap = {'100':'Thin','200':'ExtraLight','300':'Light','400':'Regular','500':'Medium','600':'SemiBold','700':'Bold','800':'ExtraBold','900':'Heavy'}
                    w = wmap.get(wgt.text, wgt.text)
                if sty is not None and sty.text:
                    s = sty.text
                return f'Font.new("{url}", Enum.FontWeight.{w}, Enum.FontStyle.{s})'
        return None

    def read_content(self, props, name):
        for p in props:
            if p.get('name') == name and p.tag == 'Content':
                u = p.find('url')
                if u is not None and u.text and u.text != 'undefined':
                    return f'"{u.text}"'
                return '""'
        return None

    def calc_bounds(self, root):
        xs_list = []
        ys_list = []
        for item in root.iter('Item'):
            props = item.find('Properties')
            if props is None:
                continue
            _, xo, _, yo = self.read_udim2(props, 'Position')
            _, sw, _, sh = self.read_udim2(props, 'Size')
            xs_list.append((xo, xo + sw))
            ys_list.append((yo, yo + sh))
        if not xs_list:
            return 0, 0, 400, 300
        self.min_x = min(x[0] for x in xs_list)
        self.min_y = min(y[0] for y in ys_list)
        max_x = max(x[1] for x in xs_list)
        max_y = max(y[1] for y in ys_list)
        self.total_w = max_x - self.min_x
        self.total_h = max_y - self.min_y
        return self.min_x, self.min_y, self.total_w, self.total_h

    def process_item(self, item, var, parent, is_top_level):
        cls = item.get('class')
        if not cls:
            return
        props = item.find('Properties')
        self.lua_lines.append(f'local {var} = Instance.new("{cls}")')
        
        if props is not None:
            n = self.read_string(props, 'Name')
            if n:
                self.lua_lines.append(f'{var}.Name = {n}')
            
            if cls not in ['UIStroke', 'UICorner', 'UIGradient', 'UIListLayout', 'UIGridLayout', 'UIPadding', 'UIAspectRatioConstraint', 'UISizeConstraint', 'UIScale']:
                xs, xo, ys, yo = self.read_udim2(props, 'Size')
                nxo = int(xo * self.scale)
                nyo = int(yo * self.scale)
                self.lua_lines.append(f'{var}.Size = UDim2.new({xs}, {nxo}, {ys}, {nyo})')
                
                pxs, pxo, pys, pyo = self.read_udim2(props, 'Position')
                if is_top_level:
                    npxo = int((pxo - self.min_x) * self.scale)
                    npyo = int((pyo - self.min_y) * self.scale)
                else:
                    npxo = int(pxo * self.scale)
                    npyo = int(pyo * self.scale)
                self.lua_lines.append(f'{var}.Position = UDim2.new({pxs}, {npxo}, {pys}, {npyo})')
            
            c = self.read_color3(props, 'BackgroundColor3')
            if c:
                self.lua_lines.append(f'{var}.BackgroundColor3 = {c}')
            
            bt = self.read_float(props, 'BackgroundTransparency')
            if bt:
                self.lua_lines.append(f'{var}.BackgroundTransparency = {bt}')
            
            bs = self.read_int(props, 'BorderSizePixel')
            if bs:
                self.lua_lines.append(f'{var}.BorderSizePixel = {bs}')
            
            v = self.read_bool(props, 'Visible')
            if v:
                self.lua_lines.append(f'{var}.Visible = {v}')
            
            tc = self.read_color3(props, 'TextColor3')
            if tc:
                self.lua_lines.append(f'{var}.TextColor3 = {tc}')
            
            tt = self.read_float(props, 'TextTransparency')
            if tt:
                self.lua_lines.append(f'{var}.TextTransparency = {tt}')
            
            ts = self.read_int(props, 'TextSize')
            if ts:
                self.lua_lines.append(f'{var}.TextSize = {ts}')
            
            tx = self.read_string(props, 'Text')
            if tx:
                self.lua_lines.append(f'{var}.Text = {tx}')
            
            tw = self.read_bool(props, 'TextWrapped')
            if tw:
                self.lua_lines.append(f'{var}.TextWrapped = {tw}')
            
            txa = self.read_token(props, 'TextXAlignment')
            if txa:
                self.lua_lines.append(f'{var}.TextXAlignment = {txa}')
            
            tya = self.read_token(props, 'TextYAlignment')
            if tya:
                self.lua_lines.append(f'{var}.TextYAlignment = {tya}')
            
            aus = self.read_token(props, 'AutomaticSize')
            if aus:
                self.lua_lines.append(f'{var}.AutomaticSize = {aus}')
            
            ff = self.read_font(props, 'FontFace')
            if ff:
                self.lua_lines.append(f'{var}.FontFace = {ff}')
            
            img = self.read_content(props, 'Image')
            if img:
                self.lua_lines.append(f'{var}.Image = {img}')
            
            it = self.read_float(props, 'ImageTransparency')
            if it:
                self.lua_lines.append(f'{var}.ImageTransparency = {it}')
            
            sc = self.read_color3(props, 'Color')
            if sc:
                self.lua_lines.append(f'{var}.Color = {sc}')
            
            st = self.read_float(props, 'Transparency')
            if st is not None:
                self.lua_lines.append(f'{var}.Transparency = {st}')
            
            sth = self.read_float(props, 'Thickness')
            if sth:
                self.lua_lines.append(f'{var}.Thickness = {sth}')
            
            asm = self.read_token(props, 'ApplyStrokeMode')
            if asm:
                self.lua_lines.append(f'{var}.ApplyStrokeMode = {asm}')
            
            ljm = self.read_token(props, 'LineJoinMode')
            if ljm:
                self.lua_lines.append(f'{var}.LineJoinMode = {ljm}')
            
            crs, cro = self.read_udim(props, 'CornerRadius')
            if cro != 0 or crs != 0:
                self.lua_lines.append(f'{var}.CornerRadius = UDim.new({crs}, {int(cro)})')
        
        self.lua_lines.append(f'{var}.Parent = {parent}')
        self.lua_lines.append('')
        
        ci = 1
        for child in item.findall('Item'):
            cv = f'{var}_{ci}'
            self.process_item(child, cv, var, False)
            ci += 1

    def convert(self, xml_str):
        try:
            root = ET.fromstring(xml_str)
        except ET.ParseError as e:
            return f'-- XML Error: {e}'
        
        self.calc_bounds(root)
        self.lua_lines = []
        
        cw = int(self.total_w * self.scale)
        ch = int(self.total_h * self.scale)
        gn = self.config.get('gui_name', 'ConvertedGui')
        
        self.lua_lines.append("local Players = game:GetService('Players')")
        self.lua_lines.append("local player = Players.LocalPlayer")
        self.lua_lines.append("local playerGui = player:WaitForChild('PlayerGui')")
        self.lua_lines.append("")
        self.lua_lines.append("local screenGui = Instance.new('ScreenGui')")
        self.lua_lines.append(f"screenGui.Name = '{gn}'")
        self.lua_lines.append("screenGui.ResetOnSpawn = false")
        self.lua_lines.append("screenGui.ZIndexBehavior = Enum.ZIndexBehavior.Sibling")
        self.lua_lines.append("screenGui.Parent = playerGui")
        self.lua_lines.append("")
        self.lua_lines.append("local mainContainer = Instance.new('Frame')")
        self.lua_lines.append("mainContainer.Name = 'MainContainer'")
        self.lua_lines.append(f"mainContainer.Size = UDim2.new(0, {cw}, 0, {ch})")
        self.lua_lines.append("mainContainer.BackgroundTransparency = 1")
        self.lua_lines.append("mainContainer.BorderSizePixel = 0")
        
        pos = self.config.get('position', 'center')
        pos_map = {
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
        if pos in pos_map:
            self.lua_lines.append(f"mainContainer.Position = {pos_map[pos][0]}")
            self.lua_lines.append(f"mainContainer.AnchorPoint = {pos_map[pos][1]}")
        else:
            self.lua_lines.append("mainContainer.Position = UDim2.new(0, 0, 0, 0)")
        
        self.lua_lines.append("mainContainer.Parent = screenGui")
        self.lua_lines.append("")
        
        idx = 1
        for item in root.findall('Item'):
            vn = f'el{idx}'
            self.process_item(item, vn, 'mainContainer', True)
            idx += 1
        
        if self.config.get('draggable'):
            self.lua_lines.append("local UIS = game:GetService('UserInputService')")
            self.lua_lines.append("local dragging, dragInput, dragStart, startPos")
            self.lua_lines.append("mainContainer.InputBegan:Connect(function(input)")
            self.lua_lines.append("\tif input.UserInputType == Enum.UserInputType.MouseButton1 or input.UserInputType == Enum.UserInputType.Touch then")
            self.lua_lines.append("\t\tdragging = true")
            self.lua_lines.append("\t\tdragStart = input.Position")
            self.lua_lines.append("\t\tstartPos = mainContainer.Position")
            self.lua_lines.append("\t\tinput.Changed:Connect(function()")
            self.lua_lines.append("\t\t\tif input.UserInputState == Enum.UserInputState.End then dragging = false end")
            self.lua_lines.append("\t\tend)")
            self.lua_lines.append("\tend")
            self.lua_lines.append("end)")
            self.lua_lines.append("mainContainer.InputChanged:Connect(function(input)")
            self.lua_lines.append("\tif input.UserInputType == Enum.UserInputType.MouseMovement or input.UserInputType == Enum.UserInputType.Touch then")
            self.lua_lines.append("\t\tdragInput = input")
            self.lua_lines.append("\tend")
            self.lua_lines.append("end)")
            self.lua_lines.append("UIS.InputChanged:Connect(function(input)")
            self.lua_lines.append("\tif input == dragInput and dragging then")
            self.lua_lines.append("\t\tlocal delta = input.Position - dragStart")
            self.lua_lines.append("\t\tmainContainer.Position = UDim2.new(startPos.X.Scale, startPos.X.Offset + delta.X, startPos.Y.Scale, startPos.Y.Offset + delta.Y)")
            self.lua_lines.append("\tend")
            self.lua_lines.append("end)")
            self.lua_lines.append("")
        
        dk = self.config.get('destroykey', 'none')
        km = {'x':'X','delete':'Delete','backspace':'Backspace','escape':'Escape','p':'P','m':'M','k':'K'}
        if dk in km:
            self.lua_lines.append(f"game:GetService('UserInputService').InputBegan:Connect(function(i,g)")
            self.lua_lines.append(f"\tif not g and i.KeyCode == Enum.KeyCode.{km[dk]} then screenGui:Destroy() end")
            self.lua_lines.append("end)")
        
        return '\n'.join(self.lua_lines)

converter = RobloxConverter()

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
        await ctx.send(f"Converting: drag={d} pos={p} scale={s} key={k} name={n}")
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
    e.add_field(name="pos", value="center/top/bottom/left/right/topleft/topright/bottomleft/bottomright/original", inline=True)
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
