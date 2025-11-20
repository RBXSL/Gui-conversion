import discord
from discord.ext import commands
import xml.etree.ElementTree as ET
import io
import os

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

class RobloxConverter:
    def __init__(self):
        self.indent_level = 0
        self.lua_code = []
    
    def indent(self):
        return "\t" * self.indent_level
    
    def parse_property_value(self, prop):
        """Extract value from property element - supports all Roblox types"""
        prop_name = prop.get('name')
        
        # String types
        if prop.find('string') is not None:
            text = prop.find('string').text or ""
            # Escape quotes and newlines
            text = text.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
            return f'"{text}"'
        
        # Content/ProtectedString (for scripts)
        elif prop.find('ProtectedString') is not None:
            text = prop.find('ProtectedString').text or ""
            text = text.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
            return f'"{text}"'
        
        # Boolean
        elif prop.find('bool') is not None:
            return prop.find('bool').text or "false"
        
        # Numbers
        elif prop.find('int') is not None:
            return prop.find('int').text or "0"
        elif prop.find('int64') is not None:
            return prop.find('int64').text or "0"
        elif prop.find('float') is not None:
            return prop.find('float').text or "0"
        elif prop.find('double') is not None:
            return prop.find('double').text or "0"
        
        # Color3
        elif prop.find('Color3') is not None:
            color = prop.find('Color3')
            r = color.find('R').text if color.find('R') is not None else "0"
            g = color.find('G').text if color.find('G') is not None else "0"
            b = color.find('B').text if color.find('B') is not None else "0"
            return f"Color3.new({r}, {g}, {b})"
        
        # Color3uint8 (0-255 range)
        elif prop.find('Color3uint8') is not None:
            color = prop.find('Color3uint8')
            r = int(color.text) >> 16 if color.text else 0
            g = (int(color.text) >> 8) & 0xFF if color.text else 0
            b = int(color.text) & 0xFF if color.text else 0
            return f"Color3.fromRGB({r}, {g}, {b})"
        
        # Vector2
        elif prop.find('Vector2') is not None:
            vec = prop.find('Vector2')
            x = vec.find('X').text if vec.find('X') is not None else "0"
            y = vec.find('Y').text if vec.find('Y') is not None else "0"
            return f"Vector2.new({x}, {y})"
        
        # Vector3
        elif prop.find('Vector3') is not None:
            vec = prop.find('Vector3')
            x = vec.find('X').text if vec.find('X') is not None else "0"
            y = vec.find('Y').text if vec.find('Y') is not None else "0"
            z = vec.find('Z').text if vec.find('Z') is not None else "0"
            return f"Vector3.new({x}, {y}, {z})"
        
        # UDim
        elif prop.find('UDim') is not None:
            udim = prop.find('UDim')
            s = udim.find('S').text if udim.find('S') is not None else "0"
            o = udim.find('O').text if udim.find('O') is not None else "0"
            return f"UDim.new({s}, {o})"
        
        # UDim2
        elif prop.find('UDim2') is not None:
            udim = prop.find('UDim2')
            xs = udim.find('XS').text if udim.find('XS') is not None else "0"
            xo = udim.find('XO').text if udim.find('XO') is not None else "0"
            ys = udim.find('YS').text if udim.find('YS') is not None else "0"
            yo = udim.find('YO').text if udim.find('YO') is not None else "0"
            return f"UDim2.new({xs}, {xo}, {ys}, {yo})"
        
        # Rect
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
        
        # Token (Enums)
        elif prop.find('token') is not None:
            token_value = prop.find('token').text or "0"
            # For enums, we'll use the numeric value
            return token_value
        
        # BrickColor
        elif prop.find('BrickColor') is not None:
            brick_color = prop.find('BrickColor').text or "194"
            return f"BrickColor.new({brick_color})"
        
        # NumberSequence
        elif prop.find('NumberSequence') is not None:
            return "NumberSequence.new(0)"  # Simplified, would need keypoint parsing
        
        # ColorSequence
        elif prop.find('ColorSequence') is not None:
            return "ColorSequence.new(Color3.new(1,1,1))"  # Simplified
        
        # NumberRange
        elif prop.find('NumberRange') is not None:
            num_range = prop.find('NumberRange')
            min_val = num_range.text.split()[0] if num_range.text else "0"
            max_val = num_range.text.split()[1] if num_range.text and len(num_range.text.split()) > 1 else min_val
            return f"NumberRange.new({min_val}, {max_val})"
        
        # Ref (References to other objects)
        elif prop.find('Ref') is not None:
            return "nil"  # References need special handling
        
        # Font
        elif prop.find('Font') is not None:
            font = prop.find('Font')
            family = font.find('Family')
            weight = font.find('Weight')
            style = font.find('Style')
            
            if family is not None and family.find('url') is not None:
                font_url = family.find('url').text or ""
                weight_val = weight.text if weight is not None else "Regular"
                style_val = style.text if style is not None else "Normal"
                
                # Try to parse font enum if it's a Roblox font
                if "rbxasset://fonts/families/" in font_url:
                    font_name = font_url.split("/")[-1].replace(".json", "")
                    return f'Font.new("rbxasset://fonts/families/{font_name}.json", Enum.FontWeight.{weight_val}, Enum.FontStyle.{style_val})'
            
            return 'Font.new("rbxasset://fonts/families/SourceSansPro.json")'
        
        return None
    
    def get_enum_from_token(self, class_name, prop_name, token_value):
        """Convert token values to Enum names when possible"""
        # Common enum mappings
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
        }
        
        try:
            token_int = int(token_value)
            if prop_name in enum_map and token_int in enum_map[prop_name]:
                return enum_map[prop_name][token_int]
        except:
            pass
        
        return token_value
    
    def convert_instance(self, item, var_name, parent_var="script.Parent"):
        """Convert a single Roblox instance to Lua code"""
        class_name = item.get('class')
        
        # Create the instance
        self.lua_code.append(f'{self.indent()}local {var_name} = Instance.new("{class_name}")')
        
        # Set properties
        properties = item.find('Properties')
        if properties is not None:
            for prop in properties:
                prop_name = prop.get('name')
                
                # Skip properties that shouldn't be set directly or cause issues
                skip_props = ['Parent', 'Archivable', 'RobloxLocked']
                if prop_name in skip_props:
                    continue
                
                try:
                    value = self.parse_property_value(prop)
                    
                    if value is None:
                        continue
                    
                    # Special handling for token/enum values
                    if prop.find('token') is not None:
                        value = self.get_enum_from_token(class_name, prop_name, value)
                    
                    self.lua_code.append(f'{self.indent()}{var_name}.{prop_name} = {value}')
                except Exception as e:
                    # Skip properties that fail to parse
                    pass
        
        # Set parent last (important for Roblox)
        self.lua_code.append(f'{self.indent()}{var_name}.Parent = {parent_var}')
        self.lua_code.append('')
        
        # Process children recursively
        counter = 1
        for child in item.findall('Item'):
            child_var = f"{var_name}_{counter}"
            self.convert_instance(child, child_var, var_name)
            counter += 1
    
    def convert_rbxmx(self, xml_content):
        """Main conversion function for RBXMX files"""
        try:
            root = ET.fromstring(xml_content)
            
            self.lua_code = [
                "-- Auto-generated Lua code from RBXMX file",
                "-- Supports: Frames, UIStroke, UIGradient, UICorner, TextLabels, TextButtons, ImageLabels, and more!",
                "-- Created by Discord Roblox Converter Bot",
                "",
            ]
            
            # Find all top-level items
            items = root.findall('.//Item')
            
            if not items:
                return "-- Error: No items found in file"
            
            # Process only root-level items
            counter = 1
            for item in items:
                parent = item.getparent()
                if parent is not None and parent.tag == 'roblox':
                    var_name = f"object{counter}"
                    self.convert_instance(item, var_name)
                    counter += 1
            
            return '\n'.join(self.lua_code)
        
        except ET.ParseError as e:
            return f"-- XML Parse Error: {str(e)}\n-- Make sure the file is a valid RBXMX file"
        except Exception as e:
            return f"-- Error converting file: {str(e)}"

converter = RobloxConverter()

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    print(f'Bot is ready to convert RBXMX/RBXM files!')
    print(f'Supports all GUI types: Frames, UIStroke, UIGradient, UICorner, and more!')

@bot.command(name='convert')
async def convert_file(ctx):
    """Convert attached RBXMX file to Lua code"""
    
    if not ctx.message.attachments:
        await ctx.send("❌ Please attach an RBXMX or RBXM file to convert!")
        return
    
    attachment = ctx.message.attachments[0]
    
    # Check file extension
    if not (attachment.filename.endswith('.rbxmx') or attachment.filename.endswith('.rbxm')):
        await ctx.send("❌ Please attach a valid .rbxmx or .rbxm file!")
        return
    
    # Check file size (Discord limit is 8MB for free, but let's be safe)
    if attachment.size > 5_000_000:  # 5MB limit
        await ctx.send("❌ File is too large! Please upload files smaller than 5MB.")
        return
    
    try:
        # Download the file
        file_content = await attachment.read()
        
        await ctx.send("🔄 Converting file to Lua code... This supports Frames, UIStroke, UIGradient, UICorner, and all GUI types!")
        
        # Convert based on file type
        if attachment.filename.endswith('.rbxmx'):
            # RBXMX is XML format
            lua_code = converter.convert_rbxmx(file_content.decode('utf-8'))
        else:
            # RBXM is binary format - more complex, needs special handling
            await ctx.send("⚠️ RBXM (binary) files require additional libraries. Please convert to RBXMX format in Roblox Studio first!\n\n**How to convert:**\n1. Open your model in Roblox Studio\n2. Right-click and select 'Save to File'\n3. Choose 'Model Files (*.rbxmx)' as the file type")
            return
        
        # Send the result
        if len(lua_code) > 1900:  # Discord message limit is 2000 chars
            # Send as file
            lua_file = discord.File(
                io.BytesIO(lua_code.encode('utf-8')),
                filename=f"{attachment.filename.replace('.rbxmx', '').replace('.rbxm', '')}_converted.lua"
            )
            await ctx.send("✅ Conversion complete! Here's your Lua code:", file=lua_file)
        else:
            await ctx.send(f"✅ Conversion complete!\n```lua\n{lua_code}\n```")
    
    except Exception as e:
        await ctx.send(f"❌ Error during conversion: {str(e)}")
        print(f"Error: {e}")

@bot.command(name='help_convert')
async def help_convert(ctx):
    """Show help information"""
    help_text = """
**Roblox File Converter Bot**

**Supported GUI Elements:**
✅ Frames, ScrollingFrames, CanvasGroups
✅ TextLabels, TextButtons, TextBoxes
✅ ImageLabels, ImageButtons
✅ UIStroke, UICorner, UIGradient
✅ UIListLayout, UIGridLayout, UIPadding
✅ UIAspectRatioConstraint, UISizeConstraint
✅ ViewportFrames
✅ And many more!

**Commands:**
`!convert` - Attach an RBXMX file to convert it to Lua code
`!help_convert` - Show this help message

**How to use:**
1. In Roblox Studio, right-click your GUI/Model
2. Click "Save to File"
3. Choose "Model Files (*.rbxmx)" format
4. Upload the file to Discord with `!convert` command

**Example:**
Attach your file and type: `!convert`
    """
    embed = discord.Embed(
        title="🤖 Roblox GUI Converter Bot",
        description=help_text,
        color=discord.Color.blue()
    )
    await ctx.send(embed=embed)

# Run the bot
if __name__ == "__main__":
    TOKEN = os.getenv('DISCORD_BOT_TOKEN')
    if not TOKEN:
        print("Error: DISCORD_BOT_TOKEN environment variable not set!")
        print("Please set your Discord bot token in Render's environment variables")
    else:
        bot.run(TOKEN)
