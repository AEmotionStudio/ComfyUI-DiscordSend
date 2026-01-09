# Contributing to ComfyUI-DiscordSend

First off, thank you for considering contributing to ComfyUI-DiscordSend! It's people like you that make this such a great tool.

## Code of Conduct

This project and everyone participating in it is governed by the [Contributor Covenant Code of Conduct](https://www.contributor-covenant.org/version/2/1/code_of_conduct/). By participating, you are expected to uphold this code.

## How Can I Contribute?

### Reporting Bugs

If you've noticed a bug, [open a new issue](https://github.com/AEmotionStudio/ComfyUI-DiscordSend/issues/new)! It's generally best if you get confirmation of your bug this way before starting to code.

### Suggesting Enhancements

If you have a feature request, [open a new issue](https://github.com/AEmotionStudio/ComfyUI-DiscordSend/issues/new)! It's generally best to get approval for your feature request this way before starting to code.

### Your First Code Contribution

Unsure where to begin contributing? You can start by looking through `good first issue` and `help wanted` issues:
* [Good first issues](https://github.com/AEmotionStudio/ComfyUI-DiscordSend/labels/good%20first%20issue) - issues which should only require a few lines of code, and a test or two.
* [Help wanted issues](https://github.com/AEmotionStudio/ComfyUI-DiscordSend/labels/help%20wanted) - issues which should be a bit more involved than `good first issue` issues.

### Pull Requests

1.  **Fork & create a branch.** [Fork the repository](https://github.com/AEmotionStudio/ComfyUI-DiscordSend/fork) and create a branch with a descriptive name. A good branch name would be (where issue #325 is the ticket you're working on): `git checkout -b 325-add-japanese-translations`
2.  **Set up your development environment.** To get started, you'll want to clone the repository and set up a virtual environment.
    ```sh
    git clone https://github.com/AEmotionStudio/ComfyUI-DiscordSend.git
    cd ComfyUI-DiscordSend
    python -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```
3.  **Implement your fix or feature.** At this point, you're ready to make your changes! Feel free to ask for help; everyone is a beginner at first.
4.  **Make a Pull Request.** At this point, you should switch back to your `master` branch and make sure it's up to date with the latest upstream version of the repository.
    ```sh
    git remote add upstream git@github.com:AEmotionStudio/ComfyUI-DiscordSend.git
    git checkout master
    git pull upstream master
    ```
    Then update your feature branch from your local copy of `master`, and push it!
    ```sh
    git checkout 325-add-japanese-translations
    git rebase master
    git push --force-with-lease origin 325-add-japanese-translations
    ```
    Finally, go to GitHub and [make a Pull Request](https://github.com/AEmotionStudio/ComfyUI-DiscordSend/compare).

## Styleguides

### Git Commit Messages

*   Use the present tense ("Add feature" not "Added feature").
*   Use the imperative mood ("Move cursor to..." not "Moves cursor to...").
*   Limit the first line to 72 characters or less.
*   Reference issues and pull requests liberally after the first line.

### Python Styleguide

All Python code should adhere to [PEP 8](https://www.python.org/dev/peps/pep-0008/).
