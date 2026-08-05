import json

async def extract_information_architecture(page, include_body_headings: bool = False):
    """
    Extracts the clean Information Architecture (IA) map focusing strictly on
    Page Names, Navigation Items, and Dropdown Submenu links.
    """
    ia_data = await page.evaluate("""(includeHeadings) => {
        function cleanText(el) {
            return (el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim().substring(0, 100);
        }
        
        const structure = {
            page_title: document.title || '',
            headings: [],
            navigation: [],
            footer_links: [],
            dropdown_menus: [],
            semantics: {}
        };
        
        // 1. Semantic landmarks
        ['header', 'nav', 'main', 'footer', 'aside'].forEach(tag => {
            if (document.querySelectorAll(tag).length > 0) {
                structure.semantics[tag] = true;
            }
        });

        // 2. Extract Headings ONLY if requested
        if (includeHeadings) {
            document.querySelectorAll('h1, h2, h3').forEach(h => {
                const text = cleanText(h);
                if (text) {
                    structure.headings.push({ level: h.tagName.toLowerCase(), text });
                }
            });
        }

        // 3. Extract Header / Main Navigation Links (Page Names)
        const headerNavs = document.querySelectorAll('header, nav, [role="navigation"]');
        const seenNavLinks = new Set();
        headerNavs.forEach(nav => {
            nav.querySelectorAll('a[href], [role="link"]').forEach(a => {
                const name = cleanText(a);
                const href = a.getAttribute('href') || '';
                if (name && href && !seenNavLinks.has(name)) {
                    seenNavLinks.add(name);
                    structure.navigation.push({ name, href });
                }
            });
        });

        // 4. Extract Dropdown & Submenu Items (up to 3 levels deep)
        const dropdownSelectors = [
            '[aria-expanded]', '[aria-haspopup="true"]', '.dropdown', '.menu-item-has-children',
            'nav li:has(ul)', '.has-dropdown', '[data-toggle="dropdown"]'
        ];
        document.querySelectorAll(dropdownSelectors.join(',')).forEach((dropdown, idx) => {
            const trigger = dropdown.querySelector('button, a, summary, [role="button"]') || dropdown;
            const categoryName = cleanText(trigger);
            const subLinks = [];
            dropdown.querySelectorAll('a[href], [role="menuitem"]').forEach(subLink => {
                const name = cleanText(subLink);
                const href = subLink.getAttribute('href') || '';
                if (name && name !== categoryName) {
                    subLinks.push({ name, href });
                }
            });
            if (categoryName && subLinks.length > 0) {
                structure.dropdown_menus.push({
                    category: categoryName,
                    items_count: subLinks.length,
                    items: subLinks
                });
            }
        });

        // 5. Extract Footer Links (Page Names)
        const footerNavs = document.querySelectorAll('footer, [role="contentinfo"]');
        const seenFooterLinks = new Set();
        footerNavs.forEach(footer => {
            footer.querySelectorAll('a[href]').forEach(a => {
                const name = cleanText(a);
                const href = a.getAttribute('href') || '';
                if (name && href && !seenFooterLinks.has(name)) {
                    seenFooterLinks.add(name);
                    structure.footer_links.push({ name, href });
                }
            });
        });

        return structure;
    }""", include_body_headings)
    return ia_data
