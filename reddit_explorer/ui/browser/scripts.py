"""
JavaScript scripts for browser customization.
"""

# Script to hide content before page loads
INITIAL_HIDE_SCRIPT = """
(function() {
    function injectStyle() {
        try {
            // Try to create and inject style
            const style = document.createElement('style');
            style.id = 'reddit-explorer-initial-hide';
            style.textContent = `
                /* Hide everything immediately */
                html.reddit-explorer-loading,
                html.reddit-explorer-loading body {
                    display: none !important;
                }
            `;
            
            const target = document.head || document.documentElement;
            if (target) {
                target.appendChild(style);
                // Add class to html element to activate the style
                document.documentElement.classList.add('reddit-explorer-loading');
                return true;
            }
        } catch (e) {
            console.log('Failed to inject style:', e);
        }
        return false;
    }

    // Try to inject immediately
    if (!injectStyle()) {
        // If failed, try again when readyState changes
        const observer = new MutationObserver((mutations, obs) => {
            if (document.documentElement) {
                injectStyle();
                obs.disconnect(); // Stop observing once we succeed
            }
        });
        
        // Start observing document for when documentElement becomes available
        observer.observe(document, {
            childList: true,
            subtree: true
        });
    }
})();
"""

# Script to hide sidebar and adjust layout
HIDE_SIDEBAR_SCRIPT = """
function adjustLayout() {
    console.log('Adjusting layout...');
    
    // Debug DOM structure
    console.log('Document body:', document.body.innerHTML.substring(0, 500));
    
    // Remove top header
    const header = document.querySelector('header');
    if (header) {
        console.log('Found header:', header.className);
        header.remove();
        console.log('Header removed');
    }
    
    // Remove back button
    const backButton = document.querySelector('pdp-back-button');
    if (backButton) {
        console.log('Found back button:', backButton.className);
        backButton.remove();
        console.log('Back button removed');
    }

    // Remove overflow menu
    const overflowMenu = document.querySelector('shreddit-post-overflow-menu');
    if (overflowMenu) {
        console.log('Found overflow menu:', overflowMenu.className);
        overflowMenu.remove();
        console.log('Overflow menu removed');
    }
    
    // Try to find the left nav container using both tag name and ID
    const leftNavContainer = document.querySelector('flex-left-nav-container#left-sidebar-container') || 
                          document.getElementById('left-sidebar-container') ||
                          document.querySelector('flex-left-nav-container');
    
    console.log('Left nav container:', leftNavContainer);
    
    if (leftNavContainer) {
        console.log('Found left nav container with classes:', leftNavContainer.className);
        // Try to find the parent container that might be the flex wrapper
        const parentContainer = leftNavContainer.parentElement;
        console.log('Parent container:', parentContainer);
        if (parentContainer) {
            console.log('Parent container classes:', parentContainer.className);
            // If parent is a flex container, remove it
            if (parentContainer.className.includes('flex')) {
                console.log('Removing parent container');
                parentContainer.remove();
            } else {
                // Otherwise just remove the nav container
                console.log('Removing nav container');
                leftNavContainer.remove();
            }
        }
    }
    
    // Find and adjust main content
    const subgridContainer = document.getElementById('subgrid-container');
    const mainContainer = document.querySelector('.main-container');
    const mainElement = document.querySelector('.main');
    
    console.log('Main elements:', {
        subgridContainer: subgridContainer?.className,
        mainContainer: mainContainer?.className,
        mainElement: mainElement?.className
    });
    
    if (mainElement) {
        console.log('Found main element, moving to top of document...');
        
        // Move main element to be the first child of body
        document.body.insertBefore(mainElement, document.body.firstChild);
        
        // Remove the containers if they exist
        if (mainContainer) mainContainer.remove();
        if (subgridContainer) subgridContainer.remove();
        
        // Add style to ensure main takes full width and adjust for removed header
        const style = document.createElement('style');
        style.textContent = `
            @media (min-width: 768px) {
                body {
                    padding-top: 0 !important;
                    margin: 0 !important;
                    overflow-x: hidden !important;
                }
                .main {
                    width: 100% !important;
                    max-width: 100% !important;
                    box-sizing: border-box !important;
                    padding: 24px 24px 0 24px !important;
                    margin: 0 !important;
                    display: block !important;
                    overflow-x: hidden !important;
                }
            }
        `;
        document.head.appendChild(style);
        console.log('Layout adjusted');

        // Show content with a smooth transition
        document.documentElement.classList.remove('reddit-explorer-loading');
    } else {
        console.log('Could not find main element');
    }
}

// Run immediately and after increasing delays
adjustLayout();
[1000, 2000, 3000, 4000, 5000].forEach((delay) => {
    setTimeout(() => {
        console.log(`Retrying after ${delay}ms...`);
        adjustLayout();
    }, delay);
});
"""
