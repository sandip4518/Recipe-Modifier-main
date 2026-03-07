document.addEventListener("DOMContentLoaded", () => {
    // Inject CSS for the Modal
    const style = document.createElement('style');
    // Pre-load external fonts for accurate typography matching
    style.innerHTML = `
        @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@800&family=Inter:wght@500;600&display=swap');

        .network-modal-overlay {
            position: fixed;
            top: 0;
            left: 0;
            width: 100vw;
            height: 100vh;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: rgba(240, 242, 245, 0.7);
            backdrop-filter: blur(4px);
            z-index: 100000;
            display: flex;
            align-items: center;
            justify-content: center;
            opacity: 0;
            visibility: hidden;
            transition: opacity 0.3s ease, visibility 0.3s ease;
        }
        .network-modal-overlay.active {
            opacity: 1;
            visibility: visible;
        }
        .network-modal {
            background: #ffffff;
            width: 90%;
            max-width: 360px;
            border-radius: 20px;
            overflow: hidden;
            box-shadow: 0 20px 50px rgba(0,0,0,0.1);
            text-align: center;
            transform: translateY(20px) scale(0.95);
            transition: transform 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
        }
        .network-modal-overlay.active .network-modal {
            transform: translateY(0) scale(1);
        }
        .network-modal-header {
            background-color: #f55151; /* Vibrant warning red */
            padding: 40px 20px 30px;
            display: flex;
            justify-content: center;
            align-items: center;
            transition: background-color 0.3s ease;
        }
        .network-modal-header svg {
            width: 70px;
            height: 70px;
            color: #ffffff;
            stroke-width: 2.2;
        }
        .network-modal-body {
            padding: 30px 30px 35px;
            background: #ffffff;
        }
        .network-modal-title {
            color: #3f4657; /* Deep matte grayish-blue like image */
            font-size: 28px;
            font-weight: 800;
            margin: 0 0 12px;
            letter-spacing: -0.2px;
            font-family: 'Montserrat', 'Segoe UI', sans-serif; /* Adding Montserrat for that punchy blocky look */
        }
        .network-modal-message {
            color: #727a8e; /* Lighter slate gray for better readability */
            font-size: 16px;
            line-height: 1.45;
            margin: 0 0 28px;
            font-weight: 500; /* Making message weight less dense */
            font-family: 'Inter', 'Segoe UI', sans-serif;
            padding: 0 10px; /* Slight inset for readability */
        }
        .network-modal-btn {
            background-color: #f55151;
            color: #ffffff;
            border: none;
            padding: 12px 35px;
            border-radius: 50px;
            font-size: 14px;
            font-weight: 800;
            letter-spacing: 0.5px;
            cursor: pointer;
            text-transform: uppercase;
            box-shadow: 0 6px 15px rgba(245, 81, 81, 0.3);
            transition: all 0.2s ease;
        }
        .network-modal-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 20px rgba(245, 81, 81, 0.4);
        }
        .network-modal-btn:active {
            transform: translateY(0);
        }
        
        /* Variants for Slow and Restored Networks */
        .network-modal.slow .network-modal-header { background-color: #f39c12; }
        .network-modal.slow .network-modal-btn { 
            background-color: #f39c12; 
            box-shadow: 0 6px 15px rgba(243, 156, 18, 0.3); 
        }
        .network-modal.slow .network-modal-btn:hover { box-shadow: 0 8px 20px rgba(243, 156, 18, 0.4); }
        
        .network-modal.restored .network-modal-header { background-color: #2ecc71; }
        .network-modal.restored .network-modal-btn { 
            background-color: #2ecc71; 
            box-shadow: 0 6px 15px rgba(46, 204, 113, 0.3); 
        }
        .network-modal.restored .network-modal-btn:hover { box-shadow: 0 8px 20px rgba(46, 204, 113, 0.4); }
    `;
    document.head.appendChild(style);

    // Create Modal DOM Elements
    const overlay = document.createElement("div");
    overlay.className = "network-modal-overlay";
    overlay.innerHTML = `
        <div class="network-modal">
            <div class="network-modal-header" id="network-modal-header">
                <!-- SVG Icon -->
            </div>
            <div class="network-modal-body">
                <h3 class="network-modal-title" id="network-modal-title">Warning!</h3>
                <p class="network-modal-message" id="network-modal-message"></p>
                <button class="network-modal-btn" id="network-modal-btn">CLOSE</button>
            </div>
        </div>
    `;
    document.body.appendChild(overlay);

    const modal = overlay.querySelector('.network-modal');
    const header = document.getElementById('network-modal-header');
    const title = document.getElementById('network-modal-title');
    const message = document.getElementById('network-modal-message');
    const btn = document.getElementById('network-modal-btn');

    const icons = {
        warning: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>`,
        success: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>`
    };

    let isOffline = !navigator.onLine;
    let userDismissed = false;
    let currentType = ""; // 'offline', 'slow', 'restored'

    function showModal(type, headerText, bodyText, btnText) {
        if (currentType === type && userDismissed) return;
        
        currentType = type;
        userDismissed = false;
        
        // Reset classes
        modal.className = "network-modal"; 
        if (type === 'slow') modal.classList.add('slow');
        if (type === 'restored') modal.classList.add('restored');

        header.innerHTML = type === 'restored' ? icons.success : icons.warning;
        title.textContent = headerText;
        message.textContent = bodyText;
        btn.textContent = btnText;

        overlay.classList.add('active');
    }

    function hideModal() {
        overlay.classList.remove('active');
        userDismissed = true;
    }

    btn.addEventListener('click', hideModal);

    function updateNetworkStatus() {
        if (!navigator.onLine) {
            isOffline = true;
            showModal('offline', 'Warning!', 'You are offline. Please check your internet connection.', 'CLOSE');
        } else {
            if (isOffline) {
                // Was offline, now came back online
                isOffline = false;
                showModal('restored', 'Restored!', 'Your internet connection has been restored.', 'CLOSE');
                setTimeout(() => {
                    if (currentType === 'restored') hideModal();
                }, 3000);
            } else {
                 // Check for slow connection if available
                const connection = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
                if (connection) {
                    const effectiveType = connection.effectiveType;
                    if (effectiveType === 'slow-2g' || effectiveType === '2g' || effectiveType === '3g') {
                        let speed = effectiveType === '3g' ? 'slow' : 'extremely slow';
                        showModal('slow', 'Warning!', `Your internet connection is ${speed}. Things might take longer to load.`, 'CLOSE');
                    } else {
                        // Normal speed
                        if (currentType === 'slow') {
                             hideModal();
                             currentType = '';
                        }
                    }
                }
            }
        }
    }

    // Event listeners for online/offline
    window.addEventListener("online", updateNetworkStatus);
    window.addEventListener("offline", updateNetworkStatus);

    // Initial check on load
    updateNetworkStatus();

    // Listen to connection changes if supported
    const connection = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
    if (connection) {
        connection.addEventListener('change', () => {
             userDismissed = false; // reset dismiss on change
             updateNetworkStatus();
        });
    }
});
