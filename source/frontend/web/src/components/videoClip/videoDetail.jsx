import React from 'react';
import './videoDetail.css'
import { FetchPost } from "../../resources/data-provider";
import {FormatSeconds} from "../../resources/utility"
import { Modal, ColumnLayout, Box, Tabs, Alert, Spinner, CopyToClipboard, Link } from '@cloudscape-design/components';
import VideoTrans from './videoTrans'
import VideoShots from './videoShots'

class VideoDetail extends React.Component {

    constructor(props) {
        super(props);
        this.videoRef = React.createRef();
        this.state = {
            status: "loading", // null, loading, loaded
            alert: null,
            
            item: null,
            filterText: null,

            showRequest: null,
        };

    }

    async componentDidMount() {
        if (this.state.item === null) {
          this.populateItem();    
        }
    }

    populateItem() {
        this.setState({status: "loading"});
        FetchPost("/extraction/video/get-task", {
          "TaskId": this.props.taskId,
          "DataTypes": ["Request", "VideoMetaData","DetectLabelCategoryAgg", "DetectLabelAgg", "DetectTextAgg", "DetectModerationAgg", "DetectCelebrityAgg", "DetectLogoAgg"],
          "PageSize": 30
        }, "ExtrService").then((data) => {
                var resp = data.body;
                if (data.statusCode !== 200) {
                    this.setState( {status: null, alert: data.body});
                }
                else {
                    if (resp !== null) {
                        this.setState(
                            {
                                item: resp,
                                status: null,
                                alert: null,
                            }
                        );
                    }
                }
            })
            .catch((err) => {
                this.setState( {status: null, alert: err.message});
            });  
    }


    handleProgressBarClick = e => {
        if (this.videoRef.current !== undefined && this.videoRef.current !== null) {
            this.videoRef.current.currentTime = e.timestamp;
        }
    }

    handleTimestampClick = e => {
        if (this.videoRef.current !== undefined && this.videoRef.current !== null) {
            this.videoRef.current.currentTime = e;
        }
    }

    calculateTimeDelta(timestamp1, timestamp2) {
        // Parse the timestamps into Date objects
        const date1 = new Date(timestamp1);
        const date2 = new Date(timestamp2);
      
        console.log(date1, date2);
        // Calculate the time difference in milliseconds
        const deltaMilliseconds = date2 - date1;
      
        // Return the time difference in milliseconds
        return FormatSeconds(deltaMilliseconds/1000)
      }
    
    getTabs(){
        let tabs = [
                {
                    label: "Shots",
                    id: "shot",
                    content: <VideoShots item={this.state.item} OnFrameClick={this.handleTimestampClick} />
                },
                {
                    label: "Transcription",
                    id: "transcription",
                    content: <VideoTrans taskId={this.state.item.Request.TaskId} OnSubtitleClick={this.handleTimestampClick} Language={this.state.item?.MetaData?.Audio?.Language} />
                },
            ]
        
        
        return tabs;
    }

    render() {
        return (
            <div className="clipvideodetail">
                {this.state.alert !== null && this.state.alert.length > 0?
                <Alert statusIconAriaLabel="Warning" type="warning">
                {this.state.alert}
                </Alert>:<div/>}
                <div className='close'>
                    <svg
                        onClick={this.props.onClose}
                        xmlns="http://www.w3.org/2000/svg"
                        width="24"
                        height="24"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                    >
                        <line x1="18" y1="6" x2="6" y2="18"></line>
                        <line x1="6" y1="6" x2="18" y2="18"></line>
                    </svg>
                </div>
                {this.state.item !== null?
                <div>
                    <div className='video'>
                        <div className='taskid'>
                            <CopyToClipboard
                                copyButtonText="Copy Task Id"
                                copyErrorText="Task Id failed to copy"
                                copySuccessText="Task Id copied"
                                textToCopy={this.state.item.Request.TaskId}
                                variant="icon"
                                /> Copy Task Id
                        </div>
                        <div className="request">
                            <Link onClick={()=> this.setState({showRequest: true})}>View Request</Link>
                        </div>
                        <video controls ref={this.videoRef} preload="auto" autoPlay={this.props.autoPlay !== undefined && this.props.autoPlay?true:false}>
                            <source src={this.state.item.VideoUrl} />
                        </video>
                        <div className="title">{this.state.item.Request.TaskName}</div>
                        <div className="timestamp">{new Date(this.state.item.RequestTs).toLocaleString()}</div>
                        <div className="processing">{this.state.item.ExtractionCompleteTs && "Processing time: " + this.calculateTimeDelta(this.state.item.RequestTs, this.state.item.ExtractionCompleteTs)}</div>

                        {
                                this.state.item.MetaData && this.state.item.MetaData.VideoMetaData?
                                <div>
                                    <br/>
                                    <ColumnLayout columns={3} variant="text-grid">
                                        <div>
                                            <Box variant="awsui-key-label">File size</Box>
                                            <Box>{(this.state.item.MetaData.VideoMetaData.Size/(1024*1024)).toFixed(2)} MB</Box>
                                        </div>
                                        <div>
                                            <Box variant="awsui-key-label">Video format</Box>
                                            <Box>{this.state.item.MetaData.VideoMetaData.NameFormat}</Box>
                                        </div>
                                        <div>
                                            <Box variant="awsui-key-label">Resolution</Box>
                                            <Box>{this.state.item.MetaData.VideoMetaData.Resolution[0]} X {this.state.item.MetaData.VideoMetaData.Resolution[1]}</Box>
                                        </div>
                                        <div>
                                            <Box variant="awsui-key-label">Duration</Box>
                                            <Box>{FormatSeconds(this.state.item.MetaData.VideoMetaData.Duration)}</Box>
                                        </div>
                                        <div>
                                            <Box variant="awsui-key-label">PFS (Frame per Second)</Box>
                                            <Box>{this.state.item.MetaData.VideoMetaData.Fps.toFixed(0)}</Box>
                                        </div>

                                    </ColumnLayout>
                                </div>:
                                <div/>
                            }
                            {this.state.item.Request.TaskType === "frame" &&
                            <div>
                            <div className='smartsample'>
                             <b>Smart Sampling enabled:</b>&nbsp;&nbsp;&nbsp;
                             {this.state.item.Request?.PreProcessSetting?.SmartSample !== undefined && this.state.item.Request?.PreProcessSetting?.SmartSample? "Yes": "No"}
                             </div>
                            {this.state.item.MetaData && this.state.item.MetaData.VideoFrameS3?
                                <ColumnLayout columns={3} variant="text-grid">
                                    {this.state.item.MetaData.VideoFrameS3.TotalFramesPlaned &&
                                        <div>
                                            <Box variant="awsui-key-label">Total frames based on sample interval</Box>
                                            <Box>{this.state.item.MetaData.VideoFrameS3.TotalFramesPlaned.toLocaleString()}</Box>
                                        </div>
                                    }
                                    {this.state.item.MetaData.VideoFrameS3.TotalFramesSampled &&
                                        <div>
                                            <Box variant="awsui-key-label">Total frames sampled</Box>
                                            <Box>{this.state.item.MetaData.VideoFrameS3.TotalFramesSampled.toLocaleString()} ({(this.state.item.MetaData.VideoFrameS3.TotalFramesSampled/this.state.item.MetaData.VideoFrameS3.TotalFramesPlaned * 100).toFixed(2)}%)
                                            </Box>
                                        </div>
                                    }
                                </ColumnLayout>
                            :<div/>}
                            </div>
                            }
                    </div>
                    <div className='detail'>
                        <Tabs 
                            tabs={this.getTabs()}
                        />
                    </div>
                </div>: <Spinner/>}
                <Modal size="large"
                    onDismiss={() => this.setState({showRequest: false})}
                    visible={this.state.showRequest}
                    header="Original Request"
                    >
                    <pre style={{
                        backgroundColor: '#f4f4f4',
                        padding: '1rem',
                        borderRadius: '8px',
                        whiteSpace: 'pre-wrap',
                        wordBreak: 'break-word',
                        fontFamily: 'monospace',
                        }}>
                        {JSON.stringify(this.state.item?.Request, null, 2)}
                    </pre>
                </Modal>
            </div>
        );
    }
}

export default VideoDetail;