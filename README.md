# BetaWordList

**BetaWordList** is a modern, cross-platform vocabulary analysis tool built with [Tauri](https://tauri.app/), [Svelte](https://svelte.dev/), and [Rust](https://www.rust-lang.org/). Designed for linguists, researchers, and anyone needing to build word lists from large-scale Chinese text corpora efficiently and interactively.

## 🚀 Overview

BetaWordList enables you to:

- **Load pre-trained NLP models** for Chinese word segmentation and POS tagging
- **Batch analyze** multiple text files with real-time progress feedback
- **Explore results** in a powerful, interactive table with advanced filtering and sorting
- **Export filtered results** to CSV for further analysis

## ✨ Features

- **One-Click Model Loading**  
  Just click "Load Model" and go!
- **Batch File Analysis**  
  Select and analyze multiple `.txt` files at once.
- **Real-Time Progress**  
  See which file is being processed and overall progress.
- **Interactive Results Table**  
  - Column sorting: Click any column header to sort (ascending/descending/none)
  - Fixed columns: "Word" and "POS" always visible
  - Responsive layout: Prevents column overlap
  - Hover tooltips: See full metric names and values
- **Advanced Filtering**  
  - By word length (e.g., only 2-character words)
  - By POS tag
  - By metric value with operators (`>`, `>=`, `<`, `<=`, `=`)
- **CSV Export**  
  - Download all filtered results as a CSV file
  - Smart file naming: `wordlist_results_{timestamp}.csv`
- **User Experience**  
  - Data statistics: original, filtered, and current page counts
  - Fully responsive for desktop and laptop screens

## 🛠️ Tech Stack

- **Frontend:** Svelte, TailwindCSS, Lucide Icons, shadcn-svelte
- **Backend:** Rust, Tauri
- **NLP:** LTP (Language Technology Platform), custom Rust NLP modules

## 📦 Getting Started

1. **Install dependencies:**

   ```bash
   bun install
   ```

2. **Run the app in development:**

   ```bash
   bun run tauri dev
   ```

3. **Build for production:**

   ```bash
   bun run tauri build
   ```

## 📋 TODO

- [ ] Customizable metric columns and export formats
- [ ] In-app help/documentation
- [ ] Performance optimization for extremely large corpora
- [x] Dark mode toggle

## 🤝 Contributing

Pull requests, issues, and suggestions are welcome! Please open an issue or PR if you have ideas or bug reports.

## 📄 License

[MIT](https://opensource.org/licenses/MIT)

## 🙏 Acknowledgements

This project makes use of the following open source projects:

- [Tauri](https://tauri.app/)
- [Svelte](https://svelte.dev/)
- [TailwindCSS](https://tailwindcss.com/)
- [Lucide Icons](https://lucide.dev/)
- [shadcn-svelte](https://shadcn-svelte.com/)
- [LTP](https://github.com/HIT-SCIR/ltp)
- [corpus-dispersion](https://github.com/Chaunice/corpus_dispersion)

Special thanks to the developers and communities behind these projects for their excellent work.
