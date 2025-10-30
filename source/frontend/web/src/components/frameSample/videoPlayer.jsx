import React, { Component, createRef } from 'react';

class VideoPlayer extends Component {
  constructor(props) {
    super(props);
    this.videoRef = createRef();
  }

  componentDidMount() {
    const { startTime, endTime } = this.props;

    // Wait for the metadata to load before seeking
    this.videoRef.current.addEventListener('loadedmetadata', () => {
      if (this.videoRef.current.duration > startTime) {
        this.videoRef.current.currentTime = startTime;
      }
    });

    // this.videoRef.current.addEventListener('timeupdate', () => {
    //   if (endTime && this.videoRef.current.currentTime >= endTime) {
    //     this.videoRef.current.pause();
    //   }
    // });
  }

componentDidUpdate(prevProps) {
    if (prevProps.startTime !== this.props.startTime) {
        this.videoRef.current.currentTime = this.props.startTime;
    }
  }

  render() {
    const { src, controls, autoPlay, className="video", muted=true } = this.props;

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
