import React from 'react';
import './videoFrames.css'
import { FetchPost } from "../../resources/data-provider";
import { Pagination, Spinner, ExpandableSection, Link, Modal, Box, Button, SpaceBetween, Toggle } from '@cloudscape-design/components';
import { DecimalToTimestamp } from "../../resources/utility";

class VideoFrames extends React.Component {

    constructor(props) {
        super(props);
        this.state = {
            status: null, // null, loading, loaded
            alert: null,
            pageSize: 10,
            currentPageIndex: 1,
            totalItems: 0,
            items: null,

            showBboxModal: false,
            selectedItem: null,
            selectedImageUrl: null,

            widthRatio: 0,
            heightRatio: 0,
            showBbox: true,
        };
        this.item = null;
        this.modalImgRef = React.createRef();
    }

    componentDidMount() {
        if (this.props.item.Request.TaskId !== null) {
          this.populateItems();    
        }
    }

    populateItems(fromIndex=null) {
        this.setState({status: "loading"});
        if (fromIndex === null)
            fromIndex = this.state.currentPageIndex
        
          FetchPost("/extraction/video/get-task-frames", {
              "PageSize": this.state.pageSize,
              "FromIndex": (fromIndex - 1) * this.state.pageSize,
              "TaskId": this.props.item.Request.TaskId
          }, "ExtrService").then((data) => {
                  var resp = data.body;
                  if (data.statusCode !== 200) {
                      this.setState( {status: null, alert: data.body});
                  }
                  else {
                      if (resp !== null) {
                          //console.log(items);
                          this.setState(
                              {
                                  items: resp.Frames,
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

    handleFrameClick(timestamp) {
        //alert(timestamp);
        this.props.OnFrameClick(timestamp);
    }

    checkCoordinates(str) {
        if (str === null || str === undefined) return false;

        const regex = /"coordinates"\s*:\s*\{[^}]+\}/g;
        const matches = str.match(regex);
        return matches;

    }

    extractAllCoordinates(str) {
        if (str === null || str === undefined) return null;

        const regex = /"coordinates"\s*:\s*\{[^}]+\}/g;
        const matches = str.match(regex);

        if (matches) {
            const obj = JSON.parse(str);
            return obj[Object.keys(obj)[0]]
        }

        return null;
    }

    handleImageLoad = () => {
        const img = this.modalImgRef.current;
        //console.log(img.width/img.naturalWidth, img.height/img.naturalHeight)
        this.setState({
            widthRatio: img.naturalWidth/1000* (img.width/img.naturalWidth),
            heightRatio: img.naturalHeight/1000 * (img.height/img.naturalHeight),
        });
    };

    render() {
        return (
            <div className="videoframes">
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
                <div className='frames'>
                {this.state.items !== undefined && this.state.items !== null?this.state.items.map((l,i)=>{
                    return <div className='frame' onClick={()=>this.handleFrameClick(l.Timestamp)}>
                        <div className='ts'>{DecimalToTimestamp(l.Timestamp)} </div>
                        <img src={l.S3Url} alt={`image_${i}`} id={`#frame-container-${i}`}></img>
                        {l.SimilarityScore && <div className='score'><b>Similarity score:</b> {l.SimilarityScore}</div>}
                        {l.CustomOutputs &&  
                            <ExpandableSection headerText="Frame analysis">
                            {l.CustomOutputs.map((item, index)=>{
                                return <div className='output'>
                                    <div className='title'>
                                        {item.name} [{item.model_id}]&nbsp;&nbsp;&nbsp;
                                        {this.checkCoordinates(item.value) &&
                                        <Link onClick={()=>{this.setState({
                                            selectedItem: item, 
                                            selectedImageUrl: l.S3Url, 
                                            showBboxModal: true,
                                            showBbox: true
                                        })}}>View bounding boxes</Link>}
                                        
                                    </div>
                                    {item.value}
                                </div>
                            })}
                            </ExpandableSection>}
                    </div>
                }):<div/>}
                </div>
                <Modal
                    onDismiss={() => this.setState({showBboxModal: false})}
                    visible={this.state.showBboxModal}
                    header="Frame Bounding Boxes"
                    size='large'
                    footer={
                        <Box float="right">
                          <SpaceBetween direction="horizontal" size="xs">
                            <Button variant="link" onClick={() => this.setState({showBboxModal: false})}>Close</Button>
                          </SpaceBetween>
                        </Box>
                      }
                >
                    <div className='framebbox'>
                        <img 
                            ref={this.modalImgRef} 
                            src={this.state.selectedImageUrl} 
                            alt={`image_frame`}
                            onLoad={this.handleImageLoad}>
                        </img>
                        {this.state.showBbox && this.state.widthRatio > 0 && this.extractAllCoordinates(this.state.selectedItem?.value)?.map((coord, i) => (
                            <div key={i}
                                className="coord-box"
                                style={{
                                    left: coord.coordinates.x * this.state.widthRatio,
                                    top: coord.coordinates.y * this.state.heightRatio,
                                    width: coord.coordinates.width * this.state.widthRatio,
                                    height: coord.coordinates.height * this.state.heightRatio,
                                }}
                            >
                                <div className="coord-label">
                                    {coord.name}
                                </div>
                            </div>
                        ))}
                        <br/>
                        <Toggle
                            onChange={({ detail }) =>
                                this.setState({showBbox: detail.checked})
                            }
                            checked={this.state.showBbox}
                            >
                            Display bounding boxes
                        </Toggle>
                    </div>
                </Modal>
                {this.state.status === "loading"?<Spinner/>:<div/>}
            </div>
        );
    }
}

export default VideoFrames;