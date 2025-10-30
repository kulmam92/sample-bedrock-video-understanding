import React, { Component, createRef } from 'react';

class VideoPlayer extends Component {
  constructor(props) {
    super(props);
    this.videoRef = createRef();
    this.handleTimeUpdate = this.handleTimeUpdate.bind(this);
  }

  componentDidMount() {
    const video = this.videoRef.current;
    const { startTime } = this.props;

    // Wait for metadata to load before seeking to startTime
    video.addEventListener('loadedmetadata', () => {
      if (startTime != null && startTime < video.duration) {
        video.currentTime = startTime;
      }
    });

    // Listen for time updates to stop at endTime
    video.addEventListener('timeupdate', this.handleTimeUpdate);
  }

  componentDidUpdate(prevProps) {
    const video = this.videoRef.current;
    const { src, startTime } = this.props;

    // Handle source changes
    if (prevProps.src !== src) {
      video.src = src;
      video.load();
    }

    // Handle startTime changes
    if (prevProps.startTime !== startTime && startTime != null) {
      video.currentTime = startTime;
      if (this.props.autoPlay) video.play();
    }
  }

  componentWillUnmount() {
    const video = this.videoRef.current;
    video.removeEventListener('timeupdate', this.handleTimeUpdate);
  }

  handleTimeUpdate() {
    const { endTime } = this.props;
    const video = this.videoRef.current;

    if (endTime != null && video.currentTime >= endTime) {
      video.pause();
    }
  }

  render() {
    const { src, controls = true, autoPlay = false, className = "video", muted = true } = this.props;

    return (
      <video
        ref={this.videoRef}
        controls={controls}
        autoPlay={autoPlay}
        className={className}
        muted={muted}
      >
        <source src={src} type="video/mp4" />
        Your browser does not support the video tag.
      </video>
    );
  }
}

export default VideoPlayer;
