const socket = io();


document.addEventListener('DOMContentLoaded', () => {
    const code = document.getElementById("room_code").textContent;
    const username = localStorage.getItem('username');
    const messageInput = document.getElementById('message');
    const sendMessageForm = document.getElementById('sendMessage');

    if (!username) {
        alert('No username found in localStorage. Please set your username before joining a chatroom.');
        window.location.href = '/'; // Redirect to a suitable page if username is missing
        return;
    }

    loadUserSettings();
    // Emit join event with username

    socket.emit('join', { code: code, username: username });

    // Listen for new messages
    socket.on('update', data => {
        const consoleElement = document.getElementById('chat');
        const div = document.createElement('div');

        const strong = document.createElement('strong');
        strong.textContent = data.username;
        applyUsernameSettings(strong);


        consoleElement.appendChild(div);
        consoleElement.scrollTop = consoleElement.scrollHeight;

        div.appendChild(strong);
        div.appendChild(document.createTextNode(`: ${data.message}`));

        consoleElement.appendChild(div);
        consoleElement.scrollTop = consoleElement.scrollHeight;  // Auto-scroll to the bottom
    });

    socket.on('user_join', data => {
        const userPanel = document.getElementById("user_panel");
        const div = document.createElement('div');
        div.classList.add("text-base");
        div.classList.add("p-2")
        div.textContent = data.username;
        userPanel.appendChild(div);
    });

    // Handle message sending and Enter/Shift+Enter behavior

    messageInput.addEventListener('keydown', function(event) {
        if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault(); // Prevent newline
            sendMessageForm.requestSubmit(); // Send the message
        }
    });

    sendMessageForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        socket.emit('new_message', { code: code, "username": username, "message": messageInput.value });
        messageInput.value = '';
    });




});

function loadUserSettings() {
    const settings = JSON.parse(localStorage.getItem('userSettings'));
    if (settings) {
        applyUserSettings(settings);
    }
}

function applyUserSettings(settings) {
    // Apply background color
    if (settings.bgColor) {
        document.body.style.backgroundColor = settings.bgColor;
    }
    // Apply <p> font and color
    if (settings.pFont) {
        document.querySelectorAll('p').forEach(p => p.style.fontFamily = settings.pFont);
    }
    if (settings.pColor) {
        document.querySelectorAll('p').forEach(p => p.style.color = settings.pColor);
    }
}

function applyUsernameSettings(strongElement) {
    const settings = JSON.parse(localStorage.getItem('userSettings'));
    if (settings) {
        // Apply username font and color to the strong element
        if (settings.usernameFont) {
            strongElement.style.fontFamily = settings.usernameFont;
        }
        if (settings.usernameColor) {
            strongElement.style.color = settings.usernameColor;
        }
    }
}
