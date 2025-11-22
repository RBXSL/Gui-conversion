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

def parse_xml(xml_str):
    root = ET.fromstring(xml_str)
    elements = []
    
    for item in root.findall('Item'):
        el = parse_item(item)
        if el:
            elements.append(el)
    
    return elements

def parse_item(item):
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
                if u is not None and u.text and u.text != 'undefined':
                    data[name] = u.text
                else:
                    data[name] = ''
    
    for child in item.findall('Item'):
        c = parse_item(child)
        if c:
            data['children'].append(c)
    
    return data

def calc_bounds(elements):
    min_x = float('inf')
    min_y = float('inf')
    max_x = float('-inf')
    max_y = float('-inf')
    
    for el in elements:
        pos = el.get('Position', {'xs':0,'xo':0,'ys':0,'yo':0})
        size = el.get('Size', {'xs':0,'xo':0,'ys':0,'yo':0})
        
        x = pos['xo']
        y = pos['yo']
        w = size['xo']
        h = size['yo']
        
        if x < min_x:
            min_x = x
        if y < min_y:
            min_y = y
        if x + w > max_x:
            max_x = x + w
        if y + h > max_y:
            max_y = y + h
    
    return min_x, min_y, max_x - min_x, max_y - min_y

def enum_val(name, v):
    m = {
        'ApplyStrokeMode': {0: 'Enum.ApplyStrokeMode.Contextual', 1: 'Enum.ApplyStrokeMode.Border'},
        'LineJoinMode': {0: 'Enum.LineJoinMode.Round', 1: 'Enum.LineJoinMode.Bevel', 2: 'Enum.LineJoinMode.Miter'},
        'TextXAlignment': {0: 'Enum.TextXAlignment.Center', 1: 'Enum.TextXAlignment.Left', 2: 'Enum.TextXAlignment.Right'},
        'TextYAlignment': {0: 'Enum.TextYAlignment.Center', 1: 'Enum.TextYAlignment.Top', 2: 'Enum.TextYAlignment.Bottom'},
        'AutomaticSize': {0: 'Enum.AutomaticSize.None', 1: 'Enum.AutomaticSize.X', 2: 'Enum.AutomaticSize.Y', 3: 'Enum.AutomaticSize.XY'},
    }
    return m.get(name, {}).get(v, str(v))

def generate_lua(elements, config):
    lines = []
    w = lines.append
    
    min_x, min_y, total_w, total_h = calc_bounds(elements)
    scale = config.get('scale', 1.0)
    gn = config.get('gui_name', 'ConvertedGui')
    
    cw = int(total_w * scale)
    ch = int(total_h * scale)
    
    w("local Players = game:GetService('Players')")
    w("local player = Players.LocalPlayer")
    w("local playerGui = player:WaitForChild('PlayerGui')")
    w("")
    w("local screenGui = Instance.new('ScreenGui')")
    w(f"screenGui.Name = '{gn}'")
    w("screenGui.ResetOnSpawn = false")
    w("screenGui.ZIndexBehavior = Enum.ZIndexBehavior.Sibling")
    w("screenGui.Parent = playerGui")
    w("")
    w("local main = Instance.new('Frame')")
    w("main.Name = 'Main'")
    w(f"main.Size = UDim2.new(0, {cw}, 0, {ch})")
    w("main.BackgroundTransparency = 1")
    w("main.BorderSizePixel = 0")
    
    pos = config.get('position', 'center')
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
        w(f"main.Position = {pm[pos][0]}")
        w(f"main.AnchorPoint = {pm[pos][1]}")
    
    w("main.Parent = screenGui")
    w("")
    
    for i, el in enumerate(elements):
        write_element(lines, el, f'el{i+1}', 'main', min_x, min_y, scale, True)
    
    if config.get('draggable'):
        w("local UIS = game:GetService('UserInputService')")
        w("local dragging, dragInput, dragStart, startPos")
        w("main.InputBegan:Connect(function(input)")
        w("\tif input.UserInputType == Enum.UserInputType.MouseButton1 or input.UserInputType == Enum.UserInputType.Touch then")
        w("\t\tdragging = true")
        w("\t\tdragStart = input.Position")
        w("\t\tstartPos = main.Position")
        w("\t\tinput.Changed:Connect(function()")
        w("\t\t\tif input.UserInputState == Enum.UserInputState.End then dragging = false end")
        w("\t\tend)")
        w("\tend")
        w("end)")
        w("main.InputChanged:Connect(function(input)")
        w("\tif input.UserInputType == Enum.UserInputType.MouseMovement or input.UserInputType == Enum.UserInputType.Touch then")
        w("\t\tdragInput = input")
        w("\tend")
        w("end)")
        w("UIS.InputChanged:Connect(function(input)")
        w("\tif input == dragInput and dragging then")
        w("\t\tlocal delta = input.Position - dragStart")
        w("\t\tmain.Position = UDim2.new(startPos.X.Scale, startPos.X.Offset + delta.X, startPos.Y.Scale, startPos.Y.Offset + delta.Y)")
        w("\tend")
        w("end)")
        w("")
    
    dk = config.get('destroykey', 'none')
    km = {'x':'X','delete':'Delete','backspace':'Backspace','escape':'Escape','p':'P','m':'M','k':'K'}
    if dk in km:
        w(f"game:GetService('UserInputService').InputBegan:Connect(function(i,g)")
        w(f"\tif not g and i.KeyCode == Enum.KeyCode.{km[dk]} then screenGui:Destroy() end")
        w("end)")
    
    return '\n'.join(lines)

def write_element(lines, el, var, parent, min_x, min_y, scale, is_top):
    w = lines.append
    cls = el['class']
    
    w(f"local {var} = Instance.new('{cls}')")
    
    # Name
    if 'Name' in el:
        nm = str(el['Name']).replace('\\', '\\\\').replace('"', '\\"').replace('\n', '')
        w(f'{var}.Name = "{nm}"')
    
    # Size (only for non-UI elements)
    if cls not in ['UIStroke', 'UICorner', 'UIGradient', 'UIListLayout', 'UIGridLayout', 'UIPadding']:
        if 'Size' in el:
            sz = el['Size']
            xo = int(sz['xo'] * scale)
            yo = int(sz['yo'] * scale)
            w(f"{var}.Size = UDim2.new({sz['xs']}, {xo}, {sz['ys']}, {yo})")
        
        # Position
        if 'Position' in el:
            ps = el['Position']
            if is_top:
                xo = int((ps['xo'] - min_x) * scale)
                yo = int((ps['yo'] - min_y) * scale)
            else:
                xo = int(ps['xo'] * scale)
                yo = int(ps['yo'] * scale)
            w(f"{var}.Position = UDim2.new({ps['xs']}, {xo}, {ps['ys']}, {yo})")
    
    # BackgroundColor3
    if 'BackgroundColor3' in el:
        c = el['BackgroundColor3']
        w(f"{var}.BackgroundColor3 = Color3.new({c['r']}, {c['g']}, {c['b']})")
    
    # BackgroundTransparency
    if 'BackgroundTransparency' in el:
        w(f"{var}.BackgroundTransparency = {el['BackgroundTransparency']}")
    
    # BorderSizePixel
    if 'BorderSizePixel' in el:
        w(f"{var}.BorderSizePixel = {el['BorderSizePixel']}")
    
    # Visible
    if 'Visible' in el:
        w(f"{var}.Visible = {str(el['Visible']).lower()}")
    
    # TextColor3
    if 'TextColor3' in el:
        c = el['TextColor3']
        w(f"{var}.TextColor3 = Color3.new({c['r']}, {c['g']}, {c['b']})")
    
    # TextTransparency
    if 'TextTransparency' in el:
        w(f"{var}.TextTransparency = {el['TextTransparency']}")
    
    # TextSize
    if 'TextSize' in el:
        w(f"{var}.TextSize = {el['TextSize']}")
    
    # Text
    if 'Text' in el:
        txt = str(el['Text']).replace('\\', '\\\\').replace('"', '\\"').replace('\n', '')
        w(f'{var}.Text = "{txt}"')
    
    # TextWrapped
    if 'TextWrapped' in el:
        w(f"{var}.TextWrapped = {str(el['TextWrapped']).lower()}")
    
    # TextXAlignment
    if 'TextXAlignment' in el:
        w(f"{var}.TextXAlignment = {enum_val('TextXAlignment', el['TextXAlignment'])}")
    
    # TextYAlignment
    if 'TextYAlignment' in el:
        w(f"{var}.TextYAlignment = {enum_val('TextYAlignment', el['TextYAlignment'])}")
    
    # AutomaticSize
    if 'AutomaticSize' in el:
        w(f"{var}.AutomaticSize = {enum_val('AutomaticSize', el['AutomaticSize'])}")
    
    # FontFace
    if 'FontFace' in el:
        f = el['FontFace']
        w(f'{var}.FontFace = Font.new("{f["url"]}", Enum.FontWeight.{f["weight"]}, Enum.FontStyle.{f["style"]})')
    
    # Image
    if 'Image' in el and el['Image']:
        w(f'{var}.Image = "{el["Image"]}"')
    
    # ImageTransparency
    if 'ImageTransparency' in el:
        w(f"{var}.ImageTransparency = {el['ImageTransparency']}")
    
    # UIStroke properties
    if 'Color' in el:
        c = el['Color']
        w(f"{var}.Color = Color3.new({c['r']}, {c['g']}, {c['b']})")
    
    if 'Transparency' in el:
        w(f"{var}.Transparency = {el['Transparency']}")
    
    if 'Thickness' in el:
        w(f"{var}.Thickness = {el['Thickness']}")
    
    if 'ApplyStrokeMode' in el:
        w(f"{var}.ApplyStrokeMode = {enum_val('ApplyStrokeMode', el['ApplyStrokeMode'])}")
    
    if 'LineJoinMode' in el:
        w(f"{var}.LineJoinMode = {enum_val('LineJoinMode', el['LineJoinMode'])}")
    
    # UICorner
    if 'CornerRadius' in el:
        cr = el['CornerRadius']
        w(f"{var}.CornerRadius = UDim.new({cr['s']}, {int(cr['o'])})")
    
    w(f"{var}.Parent = {parent}")
    w("")
    
    # Children
    for i, child in enumerate(el.get('children', [])):
        write_element(lines, child, f'{var}_{i+1}', var, min_x, min_y, scale, False)

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
        
        elements = parse_xml(xml)
        
        d = drag.lower() == 'true'
        vp = ['center','top','bottom','left','right','topleft','topright','bottomleft','bottomright','original']
        p = pos.lower() if pos.lower() in vp else 'center'
        s = scl if 0.1 <= scl <= 5.0 else 1.0
        vk = ['none','x','delete','backspace','escape','p','m','k']
        k = key.lower() if key.lower() in vk else 'none'
        n = name.replace('_',' ')
        
        await ctx.send(f"Converting: drag={d} pos={p} scale={s} key={k}")
        
        config = {'draggable': d, 'position': p, 'scale': s, 'destroykey': k, 'gui_name': n}
        lua = generate_lua(elements, config)
        
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
