const form = document.getElementById('myform');
const promptInput = document.getElementById('prompt');

let query = '';
const Id = 'addbc075-8aa8-4652-96bc-bafb730c5e5a';

const url = window.BACKEND_URL;

form.addEventListener('submit', async function (event) {
    event.preventDefault();

    query = promptInput.value;
    if (!query) return;

    addUserMessage(query);
    promptInput.value = '';

    const data = await getResult(Id);

    if (data && data.result) {
      const cleanedText = cleanPythonString(data.result);

      addAssistantMessage(cleanedText);
    }
});

// Helper function to clean Python string chunks and tuple artifacts
function cleanPythonString(rawStr) {
    if (!rawStr) return '';
    let cleaned = rawStr.trim();

    // 1. Remove leading '(' and any starting quote
    if (cleaned.startsWith('(')) {
        cleaned = cleaned.substring(1).trim();
    }
    if (cleaned.startsWith("'") || cleaned.startsWith('"')) {
        cleaned = cleaned.substring(1);
    }

    // 2. Remove trailing Python tuple artifacts like '),', '),''', or just ')'
    cleaned = cleaned.replace(/\s*\),\s*['"]*$/, ''); // Removes ),'' or ),' at the end
    cleaned = cleaned.replace(/\s*\)\s*$/, '');       // Removes trailing closing parenthesis

    // 3. Remove a trailing quote if it was left hanging from the wrapper
    if ((cleaned.endsWith("'") || cleaned.endsWith('"')) && !cleaned.endsWith("\\'")) {
        cleaned = cleaned.substring(0, cleaned.length - 1);
    }

    // 4. Split by newlines and unquote individual Python string pieces
    let lines = cleaned.split('\n');
    let finalParts = [];

    for (let line of lines) {
        line = line.trim();
        // If line is wrapped in single quotes, strip them out
        if (line.startsWith("'") && line.endsWith("'")) {
            let inner = line.slice(1, -1);
            finalParts.push(inner);
        } else {
            finalParts.push(line);
        }
    }

    // 5. Join pieces back and convert literal escaped '\\n' into real line breaks
    let joined = finalParts.join('');
    return joined.replace(/\\n/g, '\n').trim();
}

async function getResult(Id) {
    try {
        const response = await fetch(
            `${url}/result?job_id=${Id}`,
            {
                method: 'GET',
                headers: {
                    'accept': '*/*'
                }
            }
        );

        if (!response.ok) {
            throw new Error(`Couldn't fetch the data: ${response.status}`);
        }

        const result = await response.json();

        if (result.state == 'pending') {
            await new Promise(resolve => setTimeout(resolve, 1000));
            return await getResult(Id);
        }

        return result;

    } catch (error) {
        console.error(error);
    }
}

function addAssistantMessage(text) {
    const chat = document.getElementById("chat");

    const message = document.createElement("div");
    message.classList.add("message", "assistant");

    // Converts your clean markdown text into formatted HTML blocks
    message.innerHTML = marked.parse(text);

    chat.appendChild(message);
    chat.scrollTop = chat.scrollHeight; // Auto-scrolls to the bottom like ChatGPT
}

function addUserMessage(text) {
    const chat = document.getElementById("chat");

    const message = document.createElement("div");
    message.classList.add("message", "User");

    message.textContent = text; // Plain text for user input

    chat.appendChild(message);
    chat.scrollTop = chat.scrollHeight;
}
