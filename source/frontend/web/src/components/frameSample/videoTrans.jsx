import React from 'react';
import './videoTrans.css'
import { DecimalToTimestamp } from "../../resources/utility";
import { Button, Pagination, Tabs, Alert, Spinner, ExpandableSection } from '@cloudscape-design/components';
import { FetchPost } from "../../resources/data-provider";

class VideoTrans extends React.Component {

    constructor(props) {
        super(props);
        this.state = {
            status: "loading", // null, loading, loaded
            alert: null,
            uploadFile: [],

            items: null,
            pageSize: 10,
            currentPageIndex: 1,
            totalItems: 0,

            showUploadModal: false,
            extractionSettingExpand: false,
            enableDetectText: true,
            enableDetectLabel: true,
            enableDetectModeration: true,
            enableDetectCelebrity: true,
            enableTranscription: true
        };
        this.item = null;
    }

    async componentDidMount() {
        if (this.state.items === null) {
          this.populateItems();    
        }
    }
    populateItems(fromIndex=null) {
        this.setState({status: "loading"});
        if (fromIndex === null)
            fromIndex = this.state.currentPageIndex

        FetchPost("/extraction/video/get-task-transcripts", {
              "PageSize": this.state.pageSize,
              "FromIndex": (fromIndex - 1) * this.state.pageSize,
              "TaskId": this.props.taskId
        }, "ExtrService").then((data) => {
                var resp = data.body;
                if (data.statusCode !== 200) {
                    this.setState( {status: null, alert: data.body});
                }
                else {
                    if (resp !== null) {
                        this.setState(
                            {
                                  items: resp.Transcripts,
                                  totalItems: resp.Total,
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

    handleSubtitleClick(timestamp) {
        //alert(timestamp);
        this.props.OnSubtitleClick(timestamp);
    }

    render() {
        return (
            <div className="videotrans">
                <div className='pager'>
                <Pagination
                    currentPageIndex={this.state.currentPageIndex}
                    onChange={({ detail }) => {
                            this.setState({currentPageIndex: detail.currentPageIndex, items:null});
                            this.populateItems(detail.currentPageIndex);
                        }
                    }
                    pagesCount={parseInt(this.state.totalItems/this.state.pageSize) + 1}
                    disabled={this.state.items === undefined || this.state.items === null || this.state.items.length === 0}
                    />
                </div>
                {this.state.items !== null && this.state.items !== undefined?
                <div>
                    <ExpandableSection headerText="Full transcription">
                    <div className="value">{this.state.items && this.state.items.map(i => i.Transcript).join(' ')}</div>
                    </ExpandableSection>

                    <div className='title'>Language code </div>
                    <div className="value">{this.props.Language}</div>
                    <br/>
                    <div className='title'>Subtitles</div>
                   {this.state.items && this.state.items.map((l,i)=>{
                            return  <div key={`subtitle_${l.StartTs}`} className='subtitle' onClick={() => {this.handleSubtitleClick(l.StartTs)}}>
                                <div className="time">{DecimalToTimestamp(l.StartTs)}</div>
                                <div className="trans">{l.Transcript}</div>
                            </div>
                        })}
                </div>
                : <Spinner/>
                }
            </div>
        );
    }
}

export default VideoTrans;