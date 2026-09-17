const form = document.getElementById('myform');
const prompt = document.getElementById('prompt');

let query = '';
const Id = 'addbc075-8aa8-4652-96bc-bafb730c5e5a';

const url = window.BACKEND_URL;
form.addEventListener('submit', async function (event) {
    event.preventDefault();

    query = prompt.value;

    addUserMessage(query)
    const data = await getResult(Id);
    addAssistantMessage(text)
    console.log(data.result[0]);
});


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
            throw new Error(
                `Couldn't fetch the data: ${response.status}`
            );
        }

        const result = await response.json();

        if (result.state =='pending') {
          await new Promise(resolve => setTimeout(resolve, 1000))
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

    message.innerHTML = marked.parse(text);

    chat.appendChild(message);
}

function addUserMessage(text) {
    const chat = document.getElementById("chat");

    const message = document.createElement("div");
    message.classList.add("message", "User");

    message.innerHTML = marked.parse(text);

    chat.appendChild(message);
}
