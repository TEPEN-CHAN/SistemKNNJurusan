// /* =========================================================
//    CHATBOT RIASEC + KNN
//    FILE : static/js/chatbot.js
//    AUTHOR : ChatGPT
// ========================================================= */

// /* =========================================================
//    ELEMENT
// ========================================================= */

// const chatForm = document.getElementById("chatForm");
// const chatInput = document.getElementById("chatInput");
// const chatBody = document.getElementById("chatBody");

// const progressBar = document.getElementById("progressBar");
// const progressText = document.getElementById("progressText");

// const btnSend = document.getElementById("btnSend");

// const typingBox = document.getElementById("typingBox");

// /* =========================================================
//    VARIABLE
// ========================================================= */

// let totalQuestion = 42;
// let currentQuestion = 0;

// let isLoading = false;

// /* =========================================================
//    AUTO SCROLL
// ========================================================= */

// function scrollBottom() {

//     chatBody.scrollTop = chatBody.scrollHeight;
// }

// /* =========================================================
//    UPDATE PROGRESS
// ========================================================= */

// function updateProgress() {

//     let percent = Math.round(
//         (currentQuestion / totalQuestion) * 100
//     );

//     progressBar.style.width = percent + "%";

//     progressText.innerHTML =
//         currentQuestion +
//         " / " +
//         totalQuestion;
// }

// /* =========================================================
//    ADD MESSAGE USER
// ========================================================= */

// function addUserMessage(message) {

//     const wrapper = document.createElement("div");

//     wrapper.className =
//         "d-flex justify-content-end mb-3";

//     wrapper.innerHTML = `
//         <div class="chat-user-message">
//             ${escapeHtml(message)}
//         </div>
//     `;

//     chatBody.appendChild(wrapper);

//     scrollBottom();
// }

// /* =========================================================
//    ADD MESSAGE BOT
// ========================================================= */

// function addBotMessage(message) {

//     const wrapper = document.createElement("div");

//     wrapper.className =
//         "d-flex justify-content-start mb-3";

//     wrapper.innerHTML = `
//         <div class="chat-bot-message">
//             ${message}
//         </div>
//     `;

//     chatBody.appendChild(wrapper);

//     scrollBottom();
// }

// /* =========================================================
//    ADD SYSTEM MESSAGE
// ========================================================= */

// function addSystemMessage(message) {

//     const wrapper = document.createElement("div");

//     wrapper.className =
//         "text-center mb-3";

//     wrapper.innerHTML = `
//         <span class="chat-system-message">
//             ${message}
//         </span>
//     `;

//     chatBody.appendChild(wrapper);

//     scrollBottom();
// }

// /* =========================================================
//    SHOW TYPING
// ========================================================= */

// function showTyping() {

//     typingBox.style.display = "flex";

//     scrollBottom();
// }

// /* =========================================================
//    HIDE TYPING
// ========================================================= */

// function hideTyping() {

//     typingBox.style.display = "none";
// }

// /* =========================================================
//    DISABLE INPUT
// ========================================================= */

// function disableInput() {

//     isLoading = true;

//     chatInput.disabled = true;
//     btnSend.disabled = true;
// }

// /* =========================================================
//    ENABLE INPUT
// ========================================================= */

// function enableInput() {

//     isLoading = false;

//     chatInput.disabled = false;
//     btnSend.disabled = false;

//     chatInput.focus();
// }

// /* =========================================================
//    ESCAPE HTML
// ========================================================= */

// function escapeHtml(text) {

//     const div = document.createElement("div");

//     div.innerText = text;

//     return div.innerHTML;
// }

// /* =========================================================
//    FORMAT RESULT CARD
// ========================================================= */

// function createResultCard(data) {

//     return `
//         <div class="result-card">

//             <div class="result-header">

//                 <div class="result-icon">
//                     <i class="bi bi-award-fill"></i>
//                 </div>

//                 <div>

//                     <div class="result-title">
//                         Hasil Rekomendasi Jurusan
//                     </div>

//                     <div class="result-subtitle">
//                         Berdasarkan Metode KNN + RIASEC
//                     </div>

//                 </div>

//             </div>

//             <div class="result-body">

//                 <div class="result-item">

//                     <span class="result-label">
//                         Nama Siswa
//                     </span>

//                     <span class="result-value">
//                         ${data.nama}
//                     </span>

//                 </div>

//                 <div class="result-item">

//                     <span class="result-label">
//                         Jurusan Rekomendasi
//                     </span>

//                     <span class="result-badge">
//                         ${data.jurusan}
//                     </span>

//                 </div>

//                 <div class="result-item">

//                     <span class="result-label">
//                         Nilai K
//                     </span>

//                     <span class="result-value">
//                         ${data.nilai_k}
//                     </span>

//                 </div>

//                 <div class="result-item">

//                     <span class="result-label">
//                         Tipe Dominan
//                     </span>

//                     <span class="result-value">
//                         ${data.tipe_riasec}
//                     </span>

//                 </div>

//             </div>

//         </div>
//     `;
// }

// /* =========================================================
//    SEND MESSAGE
// ========================================================= */

// async function sendMessage(message) {

//     if (isLoading) {
//         return;
//     }

//     if (!message.trim()) {
//         return;
//     }

//     addUserMessage(message);

//     chatInput.value = "";

//     disableInput();

//     showTyping();

//     try {

//         const response = await fetch("/proses_chatbot", {

//             method: "POST",

//             headers: {
//                 "Content-Type": "application/json"
//             },

//             body: JSON.stringify({
//                 message: message
//             })

//         });

//         const data = await response.json();

//         hideTyping();

//         /* =========================
//            RESPONSE ERROR
//         ========================= */

//         if (data.status === "error") {

//             addSystemMessage(
//                 data.message
//             );

//             enableInput();

//             return;
//         }

//         /* =========================
//            UPDATE QUESTION
//         ========================= */

//         if (data.current_question !== undefined) {

//             currentQuestion =
//                 data.current_question;

//             updateProgress();
//         }

//         /* =========================
//            BOT MESSAGE
//         ========================= */

//         if (data.reply) {

//             addBotMessage(
//                 data.reply
//             );
//         }

//         /* =========================
//            RESULT
//         ========================= */

//         if (data.finished === true) {

//             addSystemMessage(
//                 "Tes RIASEC selesai 🎉"
//             );

//             if (data.result) {

//                 const resultHtml =
//                     createResultCard(
//                         data.result
//                     );

//                 addBotMessage(
//                     resultHtml
//                 );
//             }

//             chatInput.disabled = true;

//             btnSend.disabled = true;

//             btnSend.innerHTML = `
//                 <i class="bi bi-check-circle-fill me-2"></i>
//                 Selesai
//             `;

//             return;
//         }

//         enableInput();

//     } catch (error) {

//         hideTyping();

//         console.error(error);

//         addSystemMessage(
//             "Terjadi kesalahan server"
//         );

//         enableInput();
//     }
// }

// /* =========================================================
//    FORM SUBMIT
// ========================================================= */

// chatForm.addEventListener(
//     "submit",
//     function(event) {

//         event.preventDefault();

//         const message =
//             chatInput.value;

//         sendMessage(message);
//     }
// );

// /* =========================================================
//    ENTER KEY
// ========================================================= */

// chatInput.addEventListener(
//     "keypress",
//     function(event) {

//         if (event.key === "Enter") {

//             event.preventDefault();

//             const message =
//                 chatInput.value;

//             sendMessage(message);
//         }
//     }
// );

// /* =========================================================
//    FIRST LOAD
// ========================================================= */

// window.addEventListener(
//     "load",
//     function() {

//         updateProgress();

//         scrollBottom();

//         setTimeout(function() {

//             addBotMessage(`
//                 Halo 👋<br><br>

//                 Saya adalah AI Konselor Jurusan
//                 berbasis metode KNN + RIASEC.<br><br>

//                 Saya akan membantu menentukan
//                 rekomendasi jurusan yang sesuai
//                 dengan minat dan kemampuan kamu.<br><br>

//                 Silakan jawab pertanyaan dengan jujur 😊
//             `);

//         }, 600);
//     }
// );

// /* =========================================================
//    AUTO RESIZE INPUT
// ========================================================= */

// chatInput.addEventListener(
//     "input",
//     function() {

//         this.style.height = "auto";

//         this.style.height =
//             this.scrollHeight + "px";
//     }
// );

// /* =========================================================
//    CLEAR CHAT
// ========================================================= */

// function clearChat() {

//     chatBody.innerHTML = "";

//     currentQuestion = 0;

//     updateProgress();

//     addSystemMessage(
//         "Chat berhasil dibersihkan"
//     );
// }

// /* =========================================================
//    RESTART CHATBOT
// ========================================================= */

// async function restartChatbot() {

//     try {

//         await fetch("/reset_chatbot", {
//             method: "POST"
//         });

//         location.reload();

//     } catch (error) {

//         console.error(error);
//     }
// }

// /* =========================================================
//    EXPORT GLOBAL
// ========================================================= */

// window.clearChat = clearChat;

// window.restartChatbot = restartChatbot;