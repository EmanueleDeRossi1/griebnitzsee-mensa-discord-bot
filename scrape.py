import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime

WEBHOOK_URL = os.environ.get('DISCORD_WEBHOOK_URL')

# Map day numbers (0=Monday) to German day names for URL
DAYS = {
    0: 'montag',
    1: 'dienstag', 
    2: 'mittwoch',
    3: 'donnerstag',
    4: 'freitag'
}

# Emoji mapping for different categories
CATEGORY_EMOJIS = {
    'angebot': '🍽️',
    'dessert': '🍰',
    'salat': '🥗',
    'snack': '🥖',
    'heiße theke': '🔥',
    'abend': '🌙'
}

def get_emoji_for_category(category_name):
    """Get appropriate emoji for menu category"""
    category_lower = category_name.lower()
    for key, emoji in CATEGORY_EMOJIS.items():
        if key in category_lower:
            return emoji
    return '•'

def scrape_menu():
    """Scrape the daily menu from the mensa website"""
    today = datetime.now().weekday()
    day_name = DAYS.get(today)
    
    if not day_name:  # Weekend
        return None, None
    
    url = f"https://www.imensa.de/potsdam/mensa-griebnitzsee/{day_name}.html"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Error fetching menu: {e}")
        return None, None
    
    soup = BeautifulSoup(response.content, 'html.parser')
    
    # Find all meal categories
    menu_items = []
    meal_categories = soup.find_all('div', class_='aw-meal-category')
    
    for category in meal_categories:
        # Get category name
        category_name = category.find('h3', class_='aw-meal-category-name')
        if not category_name:
            continue
            
        category_text = category_name.get_text(strip=True)
        
        # Get meal description
        meal_desc = category.find('p', class_='aw-meal-description')
        if not meal_desc:
            continue
            
        description = meal_desc.get_text(strip=True)
        
        # Get price if available
        price_elem = category.find('div', class_='aw-meal-price')
        price_text = price_elem.get_text(strip=True) if price_elem else ""
        
        # Calculate all three price tiers
        price = ""
        if price_text and '€' in price_text:
            try:
                # Extract student price
                student_price = float(price_text.replace('€', '').replace(',', '.').strip())
                # Calculate employee and guest prices (fixed markup from Studierendenwerk Potsdam)
                employee_price = student_price + 2.55
                guest_price = student_price + 3.55
                # Format all three prices (Student/Employee/Guest)
                price = f"{student_price:.2f} / {employee_price:.2f} / {guest_price:.2f} €".replace('.', ',')
            except (ValueError, AttributeError):
                price = price_text
        
        # Get dietary info (vegan, vegetarian, etc.)
        attributes = category.find('p', class_='aw-meal-attributes')
        dietary_info = ""
        if attributes:
            attr_text = attributes.get_text(strip=True)
            # Extract just the first part (vegan/vegetarian/etc)
            if 'NÄHRWERT' in attr_text:
                dietary_info = attr_text.split('NÄHRWERT')[0].strip()
            else:
                dietary_info = attr_text.split('ZUSATZ')[0].split('ALLERGEN')[0].strip()
        
        # Format the menu item
        emoji = get_emoji_for_category(category_text)
        
        # Format: • Price (Category Name) - Dietary Info
        # Description on next line
        item_text = f"• **{price}** ({category_text})"
        
        if dietary_info:
            item_text += f" `{dietary_info}`"
        
        item_text += f"\n{description}"
        
        menu_items.append(item_text)
    
    return "\n\n".join(menu_items) if menu_items else None, day_name

def send_to_discord(content, day_name):
    """Send the menu to Discord via webhook"""
    if not WEBHOOK_URL:
        print("Error: DISCORD_WEBHOOK_URL not set")
        return False
    
    # Get German day name for display
    day_names_de = {
        'montag': 'Montag',
        'dienstag': 'Dienstag',
        'mittwoch': 'Mittwoch',
        'donnerstag': 'Donnerstag',
        'freitag': 'Freitag'
    }
    
    display_day = day_names_de.get(day_name, day_name.capitalize())
    date_str = datetime.now().strftime('%d.%m.%Y')
    
    # Discord embed for prettier formatting
    embed = {
        "title": f"🍽️ Mensa Griebnitzsee — {display_day}",
        "description": content,
        "color": 0x0e3a57,  # Blue color matching the mensa website
        "footer": {
            "text": f"Speiseplan für {date_str} • Preise: Studierende / Mitarbeitende / Gäste"
        },
        "timestamp": datetime.utcnow().isoformat()
    }
    
    data = {
        "embeds": [embed],
        "username": "Mensa Bot"
    }
    
    try:
        response = requests.post(WEBHOOK_URL, json=data, timeout=10)
        response.raise_for_status()
        print(f"Successfully posted menu for {display_day}")
        return True
    except requests.RequestException as e:
        print(f"Error posting to Discord: {e}")
        return False

def main():
    """Main function"""
    menu, day_name = scrape_menu()
    
    if menu is None:
        print("No menu available (weekend or error)")
        return
    
    if not menu:
        print("Menu is empty - posting notification")
        send_to_discord("⚠️ Kein Speiseplan verfügbar", day_name)
        return
    
    # Check if content is too long for Discord (max 4096 chars in embed description)
    if len(menu) > 4000:
        # Split into multiple parts if needed
        print("Menu is too long, truncating...")
        menu = menu[:3900] + "\n\n*... (gekürzt)*"
    
    #send_to_discord(menu, day_name)
    print(menu)

if __name__ == "__main__":
    main()