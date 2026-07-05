#!/usr/bin/env node

import Anthropic from "@anthropic-ai/sdk";
import fs from "fs";
import path from "path";
import { execSync } from "child_process";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const client = new Anthropic();

async function generateComponent(spec, componentName, maxRetries = 3) {
  const componentDir = path.join(__dirname, "generated", componentName);
  const componentFile = path.join(componentDir, `${componentName}.jsx`);
  const testFile = path.join(componentDir, `${componentName}.test.jsx`);

  fs.mkdirSync(componentDir, { recursive: true });

  let attempt = 0;
  let lastError = null;

  while (attempt < maxRetries) {
    attempt++;
    console.log(
      `\n📝 Attempt ${attempt}/${maxRetries}: Generating ${componentName}...`
    );

    const prompt = buildPrompt(spec, componentName, lastError);

    try {
      const message = await client.messages.create({
        model: "claude-opus-4-1-20250805",
        max_tokens: 2048,
        messages: [
          {
            role: "user",
            content: prompt,
          },
        ],
      });

      const responseText =
        message.content[0].type === "text" ? message.content[0].text : "";

      // Extract component code (between ```jsx blocks)
      const componentMatch = responseText.match(
        /```jsx\n([\s\S]*?)\n```/
      );
      if (!componentMatch) {
        throw new Error("No JSX code block found in response");
      }

      const componentCode = componentMatch[1];

      // Extract test code (between ```jsx blocks after component)
      const testMatch = responseText.match(/```jsx\n([\s\S]*?)\n```$/);
      const testCode = testMatch ? testMatch[1] : generateDefaultTest(componentName);

      // Write files
      fs.writeFileSync(componentFile, componentCode);
      fs.writeFileSync(testFile, testCode);

      console.log(`✅ Component written to ${componentFile}`);
      console.log(`✅ Tests written to ${testFile}`);

      // Run tests
      console.log("\n🧪 Running tests...");
      try {
        execSync(`npm test -- ${componentName}.test.jsx --testPathPattern=${componentName}`, {
          cwd: __dirname,
          stdio: "inherit",
        });
        console.log(`\n✨ All tests passed for ${componentName}!`);
        return { success: true, componentFile, testFile };
      } catch (testError) {
        lastError = extractTestError(testError);
        console.error(`\n❌ Tests failed:\n${lastError}`);

        if (attempt < maxRetries) {
          console.log(`\n🔄 Retrying with error feedback...\n`);
        }
      }
    } catch (error) {
      lastError = error.message;
      console.error(`\n❌ Generation error: ${lastError}`);

      if (attempt < maxRetries) {
        console.log(`\n🔄 Retrying...\n`);
      }
    }
  }

  return {
    success: false,
    error: `Failed to generate ${componentName} after ${maxRetries} attempts. Last error: ${lastError}`,
  };
}

function buildPrompt(spec, componentName, previousError) {
  let prompt = `Generate a React component based on this specification:

Component Name: ${componentName}
Specification:
${spec}

Requirements:
1. Write clean, functional React code
2. Include JSDoc comments for props
3. Handle edge cases (null/undefined values, empty arrays, etc.)
4. Use modern React patterns (hooks, etc.)
5. Export the component as default

Return the component code in a \`\`\`jsx block.

After the component, provide Jest tests in another \`\`\`jsx block that:
1. Import the component and testing utilities
2. Test core functionality
3. Test edge cases
4. Use @testing-library/react for DOM testing

Format:
\`\`\`jsx
// Component code here
\`\`\`

\`\`\`jsx
// Test code here
\`\`\``;

  if (previousError) {
    prompt += `\n\nPrevious test failure to fix:
${previousError}

Please fix the issues and regenerate.`;
  }

  return prompt;
}

function extractTestError(error) {
  const output = error.toString();
  // Try to extract meaningful error messages
  const lines = output.split("\n");
  const relevantLines = lines
    .filter((line) => line.includes("FAIL") || line.includes("Error") || line.includes("expect"))
    .slice(0, 10);

  return relevantLines.length > 0 ? relevantLines.join("\n") : output.substring(0, 500);
}

function generateDefaultTest(componentName) {
  return `import React from 'react';
import { render, screen } from '@testing-library/react';
import ${componentName} from './${componentName}';

describe('${componentName}', () => {
  it('renders without crashing', () => {
    render(<${componentName} />);
  });

  it('renders with default props', () => {
    const { container } = render(<${componentName} />);
    expect(container).toBeInTheDocument();
  });
});
`;
}

async function main() {
  // Example: Generate a Button component
  const buttonSpec = `
A reusable Button component with:
- Support for different variants (primary, secondary, danger)
- Disabled state
- Loading state with spinner
- Icon support (left and right)
- Size variants (sm, md, lg)
- Click handler
- Accessible (ARIA labels, keyboard support)
`;

  const result = await generateComponent(buttonSpec, "Button");

  if (result.success) {
    console.log("\n🎉 Component generation successful!");
    console.log(`Component: ${result.componentFile}`);
    console.log(`Tests: ${result.testFile}`);

    // Commit to git
    try {
      console.log("\n📦 Committing to git...");
      execSync("git add .", { cwd: __dirname, stdio: "inherit" });
      execSync(
        `git commit -m "Generate ${result.componentFile.split('/').pop()} component with tests"`,
        { cwd: path.dirname(__dirname), stdio: "inherit" }
      );
      console.log("✅ Committed successfully!");
    } catch (error) {
      console.log("⚠️  Git commit skipped or failed (file may already be staged)");
    }
  } else {
    console.error(`\n❌ ${result.error}`);
    process.exit(1);
  }
}

main().catch((error) => {
  console.error("Fatal error:", error);
  process.exit(1);
});
