const form = document.getElementById('myform');
const promptInput = document.getElementById('prompt');

const url = window.BACKEND_URL;
let Lock = false;
let sessionId = localStorage.getItem("chat_session_id");
if (!sessionId) {
    sessionId = crypto.randomUUID(); // Generate a unique session ID
    localStorage.setItem("chat_session_id", sessionId);
}
promptInput.addEventListener('keydown', function (event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        form.requestSubmit();
    }
});

function scrollToBottom() {
    window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
}

form.addEventListener('submit', async function (event) {
    event.preventDefault();
    if (Lock) return;

    const query = promptInput.value.trim();
    if (!query) return;

    Lock = true;
    promptInput.disabled = true;
    promptInput.placeholder = 'Heaven is thinking...';



    const Id = await postprompt(query, null, sessionId);
    promptInput.value = '';
    promptInput.style.height = 'auto';
    console.log('_Id', Id);
    if (!Id) {

        resetInput();
        return;
    }

    const data = await getResult(Id);



});

function resetInput() {
    Lock = false;
    promptInput.disabled = false;
    promptInput.placeholder = 'Chat with Heaven';
}

function pinPrompt() {
    const element = document.querySelector('.user_prompt');
    element.style.cssText = `
        position: fixed;
        bottom: 20px;
        left: 50%;
        transform: translateX(-50%);
        display: flex;
        justify-content: center;
        z-index: 1000;
    `;
    element.style.textAlign = '';
}


async function getResult(Id) {
    try {
        const response = await fetch(
            `${url}/v2/result?job_id=${encodeURIComponent(Id)}`,
            {
                method: 'GET',
                headers: {
                  'Content-Type': 'application/json'
                }
            }
        );
        const contentType = response.headers.get('content-type');
        if (contentType && contentType.includes('application/json')) {
          result =await  response.json()
          console.log(result.status)
        if (result.status === 'PENDING' || result.status === 'STARTED') {
            await new Promise(resolve => setTimeout(resolve, 1000));
            return await getResult(Id);
        }
        if (result.status === '202 Accepted') {
            const result = await response.json();
            return result;
        }
        return result

        }

         const reader = response.body.getReader();
         console.log("Streaming started",reader);
         const decoder = new TextDecoder();
         while (true) {
             const { value, done } = await reader.read();
             if (done) break;
             const text = decoder.decode(value);
             console.log("New chunk arrived:", text);

         }






    } catch (error) {
        console.error(error);
    }
}

async function postprompt(text, idempotency, sessionId) {
    try {
        const idempotencyId = idempotency


        const body = JSON.stringify({'query':text, 'sessionId':sessionId,'idempotency_key':idempotency})

        const response = await fetch(
            `${url}/v2/agent`,
            {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: body
            }
        );

        if (!response.ok) {
            throw new Error(`Couldn't post the prompt: ${response.status}`);
        }
        const post_response = await response.json();

        if (post_response && post_response.Status === '202 Accepted') {
          return post_response.job_id;
        }
        return null;
    } catch (error) {
        console.error(error);
        return null;
    }
}
