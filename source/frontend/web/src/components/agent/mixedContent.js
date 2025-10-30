import React from 'react';
import ReactMarkdown from 'react-markdown';
import rehypeRaw from 'rehype-raw';
import './mixedContent.css'; // Import the custom CSS file

class MixedContentDisplay extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      displayedLines: [], // Lines that are currently displayed
    };
    this.currentLineIndex = 0;
    this.intervalId = null;
  }

  componentDidMount() {
    this.startDisplayingLines();
  }

  componentWillUnmount() {
    if (this.intervalId) {
      clearInterval(this.intervalId);
    }
  }

  startDisplayingLines() {
    let { content } = this.props;

    if (!content) return;

    // Remove surrounding quotes if present
    if (content.startsWith('"') && content.endsWith('"')) {
      content = content.replace(/^"|"$/g, '');
    }

    // Split content into lines
    const lines = content.replace(/\\n/g, '\n').split('\n');

    this.intervalId = setInterval(() => {
      if (this.currentLineIndex >= lines.length) {
        clearInterval(this.intervalId);
        return;
      }

      this.setState((prevState) => ({
        displayedLines: [
          ...prevState.displayedLines,
          lines[this.currentLineIndex],
        ],
      }));

      this.currentLineIndex += 1;
    }, 100); // 100ms delay between lines
  }

  render() {
    const { displayedLines } = this.state;

    if (displayedLines.length === 0) {
      return null;
    }

    return (
      <div className="mixed-content-container">
        {displayedLines.map((line, idx) => (
          <ReactMarkdown key={idx} rehypePlugins={[rehypeRaw]}>
            {line}
          </ReactMarkdown>
        ))}
      </div>
    );
  }
}

export default MixedContentDisplay;
