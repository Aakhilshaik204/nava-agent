document.addEventListener('DOMContentLoaded', () => {
    // Welcome message
    console.log("%c⚡ NAVA OS v3.2 Initialized", "color: #00f0ff; font-weight: bold; font-size: 16px; text-shadow: 0 0 10px rgba(0, 240, 255, 0.5);");
    console.log("%cNeural Thread Scheduler: ACTIVE", "color: #9ece6a; font-family: monospace;");
    console.log("%cZero-Trust Enclave: LOCKED", "color: #9ece6a; font-family: monospace;");
    
    // Simulate terminal boot sequence in the UI
    const terminalOutput = document.querySelector('.terminal-output');
    if (terminalOutput) {
        setTimeout(() => {
            const newLine = document.createElement('p');
            newLine.className = 'term-line info';
            newLine.innerHTML = 'Boot sequence completed. All systems nominal.';
            newLine.style.opacity = '0';
            terminalOutput.insertBefore(newLine, document.querySelector('.metrics-row'));
            
            // Fade in
            setTimeout(() => {
                newLine.style.transition = 'opacity 0.5s ease';
                newLine.style.opacity = '1';
            }, 50);
        }, 1000);
    }
    
    // Smooth scrolling for navigation links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const targetId = this.getAttribute('href');
            if(targetId === '#') return;
            
            const targetElement = document.querySelector(targetId);
            if(targetElement) {
                targetElement.scrollIntoView({
                    behavior: 'smooth'
                });
            }
        });
    });
});
