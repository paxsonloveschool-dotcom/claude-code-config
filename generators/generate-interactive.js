#!/usr/bin/env node

import Anthropic from "@anthropic-ai/sdk";
import fs from "fs";
import path from "path";
import { execSync } from "child_process";
import { fileURLToPath } from "url";
import readline from "readline";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const client = new Anthropic();

const rl = readline.createInterface({
  input: process.stdin,
  output: process.stdout,
});

function question(prompt) {
  return new Promise((resolve) => rl.question(prompt, resolve));
}

async function interactiveComponentGenerator() {
  console.log("\n🚀 React Component Generator with Test-Driven Validation\n");

  const componentName = await question("Component name (PascalCase): ");
  if (!componentName.match(/^[A-Z]/)) {
    console.error("❌ Component name must start with uppercase letter");
    process.exit(1);
  }

  const description = await question("Brief description of the component: ");
  const features = await question(
    "Key features (comma-separated, or press Enter to skip): "
  );
  const maxRetriesStr = await question("Max retry attempts (default: 3): ");
  const maxRetries = parseInt(maxRetriesStr) || 3;

  rl.close();

  const spec = buildSpec(componentName, description, features);
  const result = await generateComponent(spec, componentName, maxRetries);

  if (result.success) {
    console.log("\n✨ Success! Component generated and tests passing.");
    console.log(`📂 Component: ${result.componentFile}`);
    console.log(`📂 Tests: ${result.testFile}`);
    await commitGeneration(componentName);
  } else {
    console.error(`\n❌ ${result.error}`);
    process.exit(1);
  }
}

function buildSpec(componentName, description, features) {
  let spec = `Component: ${componentName}\nPurpose: ${description}`;

  if (features.trim()) {
    spec += `\n\nKey Features:\n${features
      .split(",")
      .map((f) => `- ${f.trim()}`)
      .join("\n")}`;
  }

  return spec;
}

async function generateComponent(spec, componentName, maxRetries) {
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

      const componentMatch = responseText.match(/```jsx\n([\s\S]*?)\n```/);
      if (!componentMatch) {
        throw new Error("No JSX code block found in response");
      }

      const componentCode = componentMatch[1];

      // Find second jsx block for tests
      const remainingText = responseText.substring(componentMatch.index + componentMatch[0].length);
      const testMatch = remainingText.match(/```jsx\n([\s\S]*?)\n```/);
      const testCode = testMatch
        ? testMatch[1]
        : generateDefaultTest(componentName);

      fs.writeFileSync(componentFile, componentCode);
      fs.writeFileSync(testFile, testCode);

      console.log(`✅ Component written`);
      console.log(`✅ Tests written`);

      console.log("\n🧪 Running tests...");
      try {
        execSync(`npm test -- ${componentName}.test.jsx`, {
          cwd: __dirname,
          stdio: "inherit",
        });
        console.log(`\n✨ All tests passed!`);
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
      console.error(`\n❌ Error: ${lastError}`);

      if (attempt < maxRetries) {
        console.log(`\n🔄 Retrying...\n`);
      }
    }
  }

  return {
    success: false,
    error: `Failed after ${maxRetries} attempts. Last error: ${lastError}`,
  };
}

function buildPrompt(spec, componentName, previousError) {
  let prompt = `Generate a React component based on this specification:

${spec}

Write clean, functional React code that:
1. Uses React hooks (useState, useEffect, useCallback, etc. as needed)
2. Includes JSDoc comments for all props
3. Handles edge cases (null, undefined, empty arrays, etc.)
4. Follows React best practices
5. Is highly testable
6. Exports as default export

Return the component in a \`\`\`jsx code block.

Then provide comprehensive Jest tests in another \`\`\`jsx block:
1. Test rendering without props
2. Test with various prop combinations
3. Test edge cases
4. Test user interactions
5. Use @testing-library/react for DOM testing
6. Include import statements and describe blocks

Format:
\`\`\`jsx
// Component code
\`\`\`

\`\`\`jsx
// Test code with imports
\`\`\``;

  if (previousError) {
    prompt += `\n\nPrevious test failure to fix:
${previousError}

Analyze the error and fix the issue.`;
  }

  return prompt;
}

function extractTestError(error) {
  const output = error.toString();
  const lines = output.split("\n");
  const errorLines = lines
    .filter((l) => l.includes("FAIL") || l.includes("Error") || l.includes("●"))
    .slice(0, 15);

  return errorLines.length > 0 ? errorLines.join("\n") : output.substring(0, 800);
}

function generateDefaultTest(componentName) {
  return `import React from 'react';
import { render } from '@testing-library/react';
import ${componentName} from './${componentName}';

describe('${componentName}', () => {
  test('renders successfully', () => {
    const { container } = render(<${componentName} />);
    expect(container).toBeInTheDocument();
  });
});
`;
}

async function commitGeneration(componentName) {
  try {
    const timestamp = new Date().toISOString().split("T")[0];
    const message = `feat: generate ${componentName} component with tests (${timestamp})`;

    execSync("git add generated/", { cwd: __dirname, stdio: "pipe" });
    execSync(`git commit -m "${message}"`, {
      cwd: path.dirname(__dirname),
      stdio: "pipe",
    });

    console.log("\n✅ Committed to git");
  } catch {
    console.log("\n⚠️  Git commit skipped (no changes to commit)");
  }
}

interactiveComponentGenerator().catch((error) => {
  console.error("Fatal error:", error.message);
  process.exit(1);
});
