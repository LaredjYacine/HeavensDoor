const form = document.getElementById('myform');
const promptInput = document.getElementById('prompt');

promptInput.addEventListener('keydown', function(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        form.requestSubmit();
    }
});

let query = '';
let Lock = false;

const url = window.BACKEND_URL;
form.addEventListener('submit', async function (event) {
    event.preventDefault();
    if (Lock) return;

    query = promptInput.value;
    if (!query) return;
    Lock = true;
    promptInput.disabled = true;
    promptInput.placeholder = 'Assistant is typing ';
    addUserMessage(query);
    let Id = await postprompt(query);
    promptInput.value = '';
    if (!Id){
      Lock = false;
      promptInput.disabled = false;
      promptInput.placeholder = 'Chat with heaven';
      return
    }
    const data = await getResult(Id);

    if (data && data.result) {
      const cleanedText = cleanPythonString(data.result);

      await  addAssistantMessageAnimated(cleanedText);
    }
    Lock = false;
    promptInput.disabled = false;
    promptInput.placeholder = 'Chat with heaven';
});

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

        if (result.state == 'PENDING') {
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

async function addAssistantMessageAnimated(text) {
    const chat = document.getElementById("chat");

    const message = document.createElement("div");
    message.classList.add("message", "assistant");
    chat.appendChild(message);

    let currentText = "";
    let index = 0;
    const speed = 3; // Lower number = faster typing speed (milliseconds per character)

    return new Promise((resolve) => {
        const interval = setInterval(() => {
            if (index < text.length) {
                currentText += text[index];
                message.innerHTML = marked.parse(currentText);
                chat.scrollTop = chat.scrollHeight; // Auto-scrolls smoothly
                index++;
            } else {
                clearInterval(interval);
                resolve();
            }
        }, speed);
    });
}
async function postprompt(text, idempotency ){
  try {
    if (idempotency) {
      body = `?query=${text}&idempotency=${idempotency}`
    } else {
      body = `?query=${text}`
    }
    const response = await fetch(
      `${url}/agent${body}`,
      {
        method: 'POST',
        headers: {
          'accept': '*/*'
        },
      }
    );

    if (!response.ok) {
      throw new Error(`Couldn't post the prompt: ${response.status}`);
    }
    const post_response = await response.json();
      console.log('test', post_response.job_id);

    if (post_response && post_response.status == '202 Accepted') {
      Id = post_response.job_id
      console.log('This is the Id in the func   : ' + Id);
      return Id;
    }
    return null


  } catch (error) {
    console.error(error);
    return null;
  }
}
