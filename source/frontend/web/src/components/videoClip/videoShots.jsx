import React from 'react';
import './videoShots.css'
import { FetchPost } from "../../resources/data-provider";
import { Pagination, Spinner, ExpandableSection, Popover, StatusIndicator, Container, Header } from '@cloudscape-design/components';
import { DecimalToTimestamp } from "../../resources/utility";

class VideoShots extends React.Component {

    constructor(props) {
        super(props);
        this.state = {
            status: null, // null, loading, loaded
            alert: null,
            pageSize: 10,
            currentPageIndex: 1,
            totalItems: 0,
            items: null
        };
        this.item = null;
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
        
          FetchPost("/extraction/video/get-clip-shots", {
              "PageSize": this.state.pageSize,
              "FromIndex": (fromIndex - 1) * this.state.pageSize,
              "TaskId": this.props.item.Request.TaskId,
          }, "ExtrService").then((data) => {
                  var resp = data.body;
                  if (data.statusCode !== 200) {
                      this.setState( {status: null, alert: data.body});
                  }
                  else {
                      if (resp !== null) {
                          this.setState(
                              {
                                  items: resp.Shots,
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
    render() {
        return (
            <div className="videoshots">
                {this.state.items && <div className='total'>{this.state.totalItems} shots detected</div>}
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
                <div className='shots'>
                {this.state.items !== undefined && this.state.items !== null?this.state.items.map((l,i)=>{
                    return <Container header={
                        <Header
                            variant="h2"
                            description={`[${DecimalToTimestamp(l.StartTs)} - ${DecimalToTimestamp(l.EndTs)}]`}
                            >{`Shot${l.Index} (${l.Duration.toFixed(2)}s)`}</Header>}
                        >                  
                        <div className='shot'>
                            {l.VideoUrl && 
                            <video controls>
                                <source src={l.VideoUrl} />
                            </video>}
                        </div>
                        {l.CustomOutputs && <div>
                            <ExpandableSection headerText="Shot Analysis:">
                            {l.CustomOutputs.map((item, index)=>{
                                return <div className='output'>
                                    <div className='title'>{item.name} [{item.model_id}]</div>
                                    {item.value}
                                </div>
                            })}
                            </ExpandableSection>
                        </div>}
                    </Container>
                }):<div/>}
                </div>
                {this.state.status === "loading"?<Spinner/>:<div/>}
            </div>
        );
    }
}

export default VideoShots;