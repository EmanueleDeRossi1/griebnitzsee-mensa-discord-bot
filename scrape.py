import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from difflib import SequenceMatcher

WEBHOOK_URL = os.environ.get('DISCORD_WEBHOOK_URL')

DAYS = {
    0: 'montag',
    1: 'dienstag', 
    2: 'mittwoch',
    3: 'donnerstag',
    4: 'freitag'
}


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
    # Some items are repeated, filter them out later
    seen_descriptions = []
    meal_categories = soup.find_all('div', class_='aw-meal-category')
    
    for category in meal_categories:
        # Get category name
        category_name = category.find('h3', class_='aw-meal-category-name')
        if not category_name:
            continue
            
        category_text = category_name.get_text(strip=True)

        # Skip "Abend" items
        if 'Abend' in category_text:
            continue
        
        # Get meal description
        meal_desc = category.find('p', class_='aw-meal-description')
        if not meal_desc:
            continue
            
        description = meal_desc.get_text(strip=True)

        # Skip if too similar to existing descriptions
        is_duplicate = False
        for seen in seen_descriptions:
            similarity = SequenceMatcher(None, description.lower(), seen.lower()).ratio()
            if similarity > 0.75:
                is_duplicate = True
                break
        
        if is_duplicate:
            continue

        seen_descriptions.append(description)        
        # Get price if available
        price_elem = category.find('div', class_='aw-meal-price')
        price_text = price_elem.get_text(strip=True) if price_elem else ""
        
        # Calculate all three price tiers
        price = ""
        if price_text and '€' in price_text:
            try:
                student_price = float(price_text.replace('€', '').replace(',', '.').strip())
                # Calculate employee and guest prices (fixed markup from Studierendenwerk Potsdam)
                employee_price = student_price + 2.55
                guest_price = student_price + 3.55
                price = f"{student_price:.2f} / {employee_price:.2f} / {guest_price:.2f} €".replace('.', ',')
            except (ValueError, AttributeError):
                price = price_text
                        
        # Format: • Price (Category Name) - Dietary Info
        # Description on next line
        item_text = f"• {category_text} **{price}**"
                
        item_text += f"\n{description}"
        
        menu_items.append(item_text)
    
    return "\n\n".join(menu_items) if menu_items else None, day_name

def send_to_discord(content, day_name):
    """Send the menu to Discord via webhook"""
    if not WEBHOOK_URL:
        print("Error: DISCORD_WEBHOOK_URL not set")
        return False
    
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
        "color": 0x0e3a57,
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
    
    # send_to_discord(menu, day_name)
    print(menu)

if __name__ == "__main__":
    main()
