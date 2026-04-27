// Test the agent URL field directly in browser console
// Copy and paste this into Thunderbird's Browser Console (Ctrl+Shift+J)

console.log("=== OpenMailBot Agent URL Field Test ===");

// Get the input element
const agentInput = document.getElementById("ob-agent-url");
console.log("1. Agent input element:", agentInput);

if (agentInput) {
    console.log("2. Current readonly state:", agentInput.readOnly);
    console.log("3. Current readonly attribute:", agentInput.getAttribute("readonly"));
    console.log("4. Current value:", agentInput.value);
    console.log("5. Current placeholder:", agentInput.placeholder);
    console.log("6. Current background:", agentInput.style.background);
    console.log("7. Current color:", agentInput.style.color);
    
    // Try to make it editable
    console.log("\n--- Attempting to make field editable ---");
    agentInput.readOnly = false;
    agentInput.removeAttribute("readonly");
    agentInput.style.background = "#ffffff";
    agentInput.style.color = "#000000";
    agentInput.placeholder = "http://your-server:5050";
    
    console.log("8. After changes - readonly:", agentInput.readOnly);
    console.log("9. After changes - readonly attr:", agentInput.getAttribute("readonly"));
    console.log("10. After changes - background:", agentInput.style.background);
    
    console.log("\n✅ Test complete. Try typing in the field now.");
} else {
    console.error("❌ Could not find agent input element!");
}

// Also check if MANOTR_AGENT_URL is defined
try {
    console.log("\n11. MANOTR_AGENT_URL constant:", MANOTR_AGENT_URL);
} catch (e) {
    console.error("❌ MANOTR_AGENT_URL not defined:", e.message);
}
