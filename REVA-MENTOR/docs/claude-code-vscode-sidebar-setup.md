# How to Configure Claude Code Extension in Visual Studio Code Side Panel

**Last Updated:** October 7, 2025  
**Extension Version Tested:** Claude Code for VS Code v2.0.10

This guide will help you set up the Claude Code extension in Visual Studio Code's side panel for easy access. 
You can also use this process for other chat extentions like [Codex](https://marketplace.cursorapi.com/items/?itemName=openai.chatgpt).

## Prerequisites

- Visual Studio Code installed on your system
- Internet connection for extension installation

## Step-by-Step Instructions

### Step 1: Install the Claude Code Extension

1. Open Visual Studio Code
2. Navigate to the Extensions view by clicking the Extensions icon in the Activity Bar (or press `Ctrl+Shift+X` / `Cmd+Shift+X`)
3. Search for "Claude Code" in the extensions marketplace
4. Find the official Claude Code extension by Anthropic
5. Click **Install** to add the extension to your VS Code

**Alternative:** Install directly from the marketplace link: [Claude Code Extension](https://marketplace.cursorapi.com/items/?itemName=Anthropic.claude-code)
<img width="1266" height="614" alt="Pasted Graphic 1" src="https://gist.github.com/user-attachments/assets/9443ea42-8ba8-4cb4-b05a-4909603f8f8d" />

### Step 2: Configure Activity Bar Orientation

1. Open VS Code Settings:
   - **Windows/Linux:** `Ctrl+,`
   - **macOS:** `Cmd+,`
2. In the search bar, type "activity bar orientation"
3. Find the setting: **Workbench › Appearance › Activity Bar: Orientation**
4. Change the value from "horizontal" to **"vertical"**

This step ensures the side panel layout works optimally with the Claude Code extension.
<img width="1362" height="334" alt="42c7592b3a349246aba7b412853f8a985be23012" src="https://gist.github.com/user-attachments/assets/840afa7d-2335-4ed1-8f48-2f55dc6fc4b3" />


### Step 3: Open Claude Code in Sidebar

1. Open the Command Palette:
   - **Windows/Linux:** `Ctrl+Shift+P`
   - **macOS:** `Cmd+Shift+P`
2. Type "Claude" in the command palette
3. Select **"Claude Code: Open in sidebar"** from the dropdown menu
4. The Claude Code interface will appear in the sidebar

<img width="308" height="272" alt="Claude Code Open in Side Bar" src="https://gist.github.com/user-attachments/assets/df4c049b-0335-4480-a21e-28f449e38dca" />

### Step 4: Move to Chat Panel

1. Locate the Claude Code icon in the sidebar
2. Click and drag the icon from the sidebar
3. Drop it into the chat panel area

<img width="1240" height="875" alt="Pasted Graphic 3" src="https://gist.github.com/user-attachments/assets/259ba2da-5fbb-4213-9880-e7adb0223cf2" />


## Verification

To verify the setup is working correctly:

1. You should see the Claude Code interface in the chat panel.
2. You can start a conversation with Claude by typing in the chat interface
3. The extension should be ready to assist with your coding tasks

<img width="1240" height="840" alt="Pasted Graphic 2" src="https://gist.github.com/user-attachments/assets/f9f212da-6bce-46ee-ba60-f162a862f187" />


## Troubleshooting

**Extension not appearing:** Make sure you've installed the official Claude Code extension by Anthropic, not a similar extension with a different name.

**Sidebar not showing:** Verify that the Activity Bar orientation is set to "vertical" in your VS Code settings.

**Command not found:** Ensure the extension is properly installed and VS Code has been restarted after installation.

## Additional Resources

- [Claude Code Extension Documentation](https://marketplace.cursorapi.com/items/?itemName=Anthropic.claude-code)
- [Visual Studio Code Extensions Guide](https://code.visualstudio.com/docs/editor/extension-marketplace)

---

*This guide has been tested and verified to work with Visual Studio Code and Claude Code for VS Code v2.0.10 (last updated October 7, 2025).*
